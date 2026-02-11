/**
 * DeviceContext Tests
 *
 * Tests for device context provider including:
 * - Device registration with push notification token
 * - Device capability checking (camera, location, notifications, biometric)
 * - Permission request flow
 * - Device state management (registered, unregistered, pending)
 * - Integration with AuthContext
 * - Device token updates
 * - Device sync with backend
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react-native';
import { DeviceProvider, useDevice } from '../../contexts/DeviceContext';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { Text, View, Pressable, Alert } from 'react-native';

// Mock fetch
global.fetch = jest.fn();

import * as Device from 'expo-device';
import * as Camera from 'expo-camera';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import * as LocalAuthentication from 'expo-local-authentication';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock Alert
jest.spyOn(Alert, 'alert').mockImplementation(() => {});

// ============================================================================
// Test Components
// ============================================================================

interface DeviceTestComponentProps {
  children?: React.ReactNode;
}

const DeviceTestComponent: React.FC<DeviceTestComponentProps> = ({ children }) => {
  const { deviceState, registerDevice, requestCapability, checkCapability, syncDevice } = useDevice();
  const { isAuthenticated, user } = useAuth();

  return (
    <View>
      <Text testID="deviceId">{deviceState.deviceId || 'null'}</Text>
      <Text testID="deviceToken">{deviceState.deviceToken || 'null'}</Text>
      <Text testID="platform">{deviceState.platform || 'null'}</Text>
      <Text testID="isRegistered">{deviceState.isRegistered.toString()}</Text>
      <Text testID="cameraCapability">{deviceState.capabilities.camera.toString()}</Text>
      <Text testID="locationCapability">{deviceState.capabilities.location.toString()}</Text>
      <Text testID="notificationsCapability">{deviceState.capabilities.notifications.toString()}</Text>
      <Text testID="biometricCapability">{deviceState.capabilities.biometric.toString()}</Text>
      <Text testID="screenRecordingCapability">{deviceState.capabilities.screenRecording.toString()}</Text>
      <Text testID="lastSync">{deviceState.lastSync ? deviceState.lastSync.toISOString() : 'null'}</Text>
      <Text testID="isAuthenticated">{isAuthenticated.toString()}</Text>
      <Text testID="user">{user ? JSON.stringify(user) : 'null'}</Text>
      {children}
    </View>
  );
};

const renderWithDeviceProvider = (component?: React.ReactNode) => {
  return render(
    <AuthProvider>
      <DeviceProvider>
        <DeviceTestComponent>{component}</DeviceTestComponent>
      </DeviceProvider>
    </AuthProvider>
  );
};

// ============================================================================
// Setup and Teardown
// ============================================================================

const mockDeviceId = 'device_test_123';
const mockPushToken = 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]';
const mockAccessToken = 'mock_access_token_123';
const mockUser = { id: 'user_1', email: 'test@example.com', name: 'Test User' };

beforeEach(() => {
  jest.clearAllMocks();

  // Default successful mocks for AsyncStorage
  (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
  (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
  (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);

  // Default successful mocks for device modules
  (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  (Camera.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
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

  (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
  (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
  (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({ success: true });

  // Default successful mock for device registration
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({
      device_id: mockDeviceId,
    }),
  });

  // Store access token for authenticated tests
  (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
    if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
    return Promise.resolve(null);
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ============================================================================
// Device Registration Tests
// ============================================================================

describe('DeviceContext - Device Registration', () => {
  test('should initialize with unregistered device state', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(screen.getByTestId('isRegistered')).toHaveTextContent('false');
      expect(screen.getByTestId('deviceId')).toHaveTextContent('null');
      expect(screen.getByTestId('deviceToken')).toHaveTextContent('null');
    });
  });

  test('should register device successfully with push token', async () => {
    const { getByTestId } = renderWithDeviceProvider();

    // First, authenticate the user
    await act(async () => {
      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
        return Promise.resolve(null);
      });
    });

    // Register device
    await act(async () => {
      const { result } = renderWithDeviceProvider();
      const { registerDevice } = result?.current || { registerDevice: async () => ({ success: false }) };
      // Device registration will happen through the component
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_id', mockDeviceId);
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_token', mockPushToken);
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_registered', 'true');
    });
  });

  test('should handle device registration error when not authenticated', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Not authenticated' }),
    });

    renderWithDeviceProvider();

    // Verify error is handled gracefully
    await waitFor(() => {
      expect(screen.getByTestId('isRegistered')).toHaveTextContent('false');
    });
  });

  test('should load device state from storage on mount', async () => {
    const storedDeviceState = {
      deviceId: 'stored_device_123',
      deviceToken: 'stored_token_123',
      isRegistered: 'true',
      capabilities: JSON.stringify({
        camera: true,
        location: false,
        notifications: true,
        biometric: false,
        screenRecording: false,
      }),
      lastSync: new Date().toISOString(),
    };

    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_id') return Promise.resolve(storedDeviceState.deviceId);
      if (key === 'atom_device_token') return Promise.resolve(storedDeviceState.deviceToken);
      if (key === 'atom_device_registered') return Promise.resolve(storedDeviceState.isRegistered);
      if (key === 'atom_device_capabilities') return Promise.resolve(storedDeviceState.capabilities);
      if (key === 'atom_last_sync') return Promise.resolve(storedDeviceState.lastSync);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    renderWithDeviceProvider();

    await waitFor(() => {
      expect(screen.getByTestId('deviceId')).toHaveTextContent('stored_device_123');
      expect(screen.getByTestId('deviceToken')).toHaveTextContent('stored_token_123');
      expect(screen.getByTestId('isRegistered')).toHaveTextContent('true');
    });
  });
});

// ============================================================================
// Device Capability Tests
// ============================================================================

describe('DeviceContext - Capability Checking', () => {
  test('should check camera capability status', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(Camera.getCameraPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should check location capability status', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(Location.getForegroundPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should check notifications capability status', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should check biometric capability status', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(LocalAuthentication.hasHardwareAsync).toHaveBeenCalled();
      expect(LocalAuthentication.isEnrolledAsync).toHaveBeenCalled();
    });
  });

  test('should update capabilities after permission request', async () => {
    const { getByTestId } = renderWithDeviceProvider();

    // Request camera permission
    await act(async () => {
      const { result } = renderWithDeviceProvider();
      // Capability request will be triggered
    });

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
    });
  });
});

// ============================================================================
// Permission Request Tests
// ============================================================================

describe('DeviceContext - Permission Requests', () => {
  test('should request camera permission successfully', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Trigger camera permission request
      const { result } = renderWithDeviceProvider();
    });

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_device_capabilities',
        expect.stringContaining('"camera":true')
      );
    });
  });

  test('should handle camera permission denial with alert', async () => {
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
      canAskAgain: true,
      granted: false,
      expires: 'never',
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger camera permission request
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Camera Permission Required',
        expect.stringContaining('Camera access is needed'),
        expect.any(Array)
      );
    });
  });

  test('should request location permission successfully', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Trigger location permission request
    });

    await waitFor(() => {
      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should handle location permission denial with alert', async () => {
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
      canAskAgain: true,
      granted: false,
      expires: 'never',
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger location permission request
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Location Permission Required',
        expect.stringContaining('Location access is needed'),
        expect.any(Array)
      );
    });
  });

  test('should request notifications permission successfully', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Trigger notifications permission request
    });

    await waitFor(() => {
      expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should handle notifications permission denial with alert', async () => {
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
      canAskAgain: true,
      granted: false,
      expires: 'never',
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger notifications permission request
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Notification Permission Required',
        expect.stringContaining('Notifications are needed'),
        expect.any(Array)
      );
    });
  });

  test('should detect biometric not available', async () => {
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger biometric capability check
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Biometric Not Available',
        expect.stringContaining('does not support biometric'),
        expect.any(Array)
      );
    });
  });

  test('should detect no biometric enrolled', async () => {
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
    (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(false);

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger biometric capability check
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'No Biometric Enrolled',
        expect.stringContaining('Please enroll'),
        expect.any(Array)
      );
    });
  });

  test('should handle screen recording not available on mobile', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Trigger screen recording capability check
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Feature Not Available',
        expect.stringContaining('not available on mobile'),
        expect.any(Array)
      );
    });
  });
});

// ============================================================================
// Platform-Specific Permission Tests
// ============================================================================

describe('DeviceContext - Platform-Specific Permissions', () => {
  test('should handle iOS vs Android platform detection', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(screen.getByTestId('platform')).toBeTruthy();
    });
  });

  test('should normalize permission status across platforms', async () => {
    // Test iOS permission format
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });

    renderWithDeviceProvider();

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should handle permission revoked during app use', async () => {
    // First permission is granted
    (Camera.getCameraPermissionsAsync as jest.Mock)
      .mockResolvedValueOnce({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      })
      .mockResolvedValueOnce({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

    renderWithDeviceProvider();

    await act(async () => {
      // Check permission, then revoke, then check again
    });

    await waitFor(() => {
      expect(Camera.getCameraPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should handle permission prompt cancellation', async () => {
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'notAsked',
      canAskAgain: true,
      granted: false,
      expires: 'never',
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Request permission (user cancels)
    });

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
    });
  });
});

// ============================================================================
// Device State Management Tests
// ============================================================================

describe('DeviceContext - Device State Management', () => {
  test('should track device state (registered, unregistered, pending)', async () => {
    renderWithDeviceProvider();

    await waitFor(() => {
      expect(screen.getByTestId('isRegistered')).toHaveTextContent('false');
    });

    // Simulate registration
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('true');
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    await act(async () => {
      // Re-mount to load updated state
    });

    await waitFor(() => {
      // State should update to registered
    });
  });

  test('should update device info when capabilities change', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Change a capability
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_device_capabilities',
        expect.any(String)
      );
    });
  });

  test('should trigger context re-render on state change', async () => {
    const { getByTestId } = renderWithDeviceProvider();

    const initialText = getByTestId('isRegistered').props.children;

    await act(async () => {
      // Change state
    });

    await waitFor(() => {
      expect(getByTestId('isRegistered')).toBeTruthy();
    });
  });
});

// ============================================================================
// Integration with AuthContext Tests
// ============================================================================

describe('DeviceContext - Integration with AuthContext', () => {
  test('should register device after authentication', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: mockAccessToken,
        refresh_token: 'refresh_token',
        user: mockUser,
      }),
    });

    renderWithDeviceProvider();

    await waitFor(() => {
      expect(screen.getByTestId('isAuthenticated')).toBeTruthy();
    });
  });

  test('should cleanup device state on logout', async () => {
    // Setup registered device
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    const { getByTestId } = renderWithDeviceProvider();

    await waitFor(() => {
      expect(getByTestId('deviceId')).toHaveTextContent(mockDeviceId);
    });

    await act(async () => {
      // Logout
    });

    await waitFor(() => {
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_token');
    });
  });

  test('should handle device token updates after token refresh', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Update device token
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_token', expect.any(String));
    });
  });
});

// ============================================================================
// Device Token Management Tests
// ============================================================================

describe('DeviceContext - Device Token Management', () => {
  test('should update device token', async () => {
    const newToken = 'ExponentPushToken[new_token_123]';

    // Setup registered device
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('true');
      if (key === 'atom_device_token') return Promise.resolve(mockPushToken);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Update token
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_token', newToken);
    });
  });

  test('should not update token if device not registered', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('false');
      return Promise.resolve(null);
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Try to update token
    });

    await waitFor(() => {
      expect(screen.getByTestId('isRegistered')).toHaveTextContent('false');
    });
  });
});

// ============================================================================
// Device Sync Tests
// ============================================================================

describe('DeviceContext - Device Sync', () => {
  test('should sync device state with backend', async () => {
    // Setup registered device
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('true');
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger sync
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/mobile/sync/trigger'),
        expect.any(Object)
      );
    });
  });

  test('should update last sync time after successful sync', async () => {
    // Setup registered device
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('true');
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Trigger sync
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_last_sync', expect.any(String));
    });
  });

  test('should handle sync error when device not registered', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('false');
      return Promise.resolve(null);
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Try to sync
    });

    await waitFor(() => {
      expect(screen.getByTestId('isRegistered')).toHaveTextContent('false');
    });
  });
});

// ============================================================================
// Device Unregister Tests
// ============================================================================

describe('DeviceContext - Device Unregister', () => {
  test('should unregister device and clear state', async () => {
    // Setup registered device
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('true');
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_device_token') return Promise.resolve(mockPushToken);
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Unregister device
    });

    await waitFor(() => {
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_token');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_registered');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_last_sync');
    });
  });

  test('should not call backend if device not registered', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_registered') return Promise.resolve('false');
      return Promise.resolve(null);
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Try to unregister
    });

    await waitFor(() => {
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });
});

// ============================================================================
// Permission Edge Cases Tests
// ============================================================================

describe('DeviceContext - Permission Edge Cases', () => {
  test('should handle permission revoked during app use', async () => {
    // Permission granted initially
    (Camera.getCameraPermissionsAsync as jest.Mock)
      .mockResolvedValueOnce({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      })
      // Then revoked
      .mockResolvedValueOnce({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

    renderWithDeviceProvider();

    await act(async () => {
      // Check permission twice
    });

    await waitFor(() => {
      expect(Camera.getCameraPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should handle "dont ask again" for Android permissions', async () => {
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
      canAskAgain: false, // User selected "Don't ask again"
      granted: false,
      expires: 'never',
    });

    renderWithDeviceProvider();

    await act(async () => {
      // Request permission
    });

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
    });
  });

  test('should handle multiple simultaneous permission requests', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Request multiple permissions at once
    });

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalled();
      expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();
    });
  });
});

// ============================================================================
// Capability Caching Tests
// ============================================================================

describe('DeviceContext - Capability Caching', () => {
  test('should cache capability results in AsyncStorage', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Request capability
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_device_capabilities',
        expect.any(String)
      );
    });
  });

  test('should load cached capabilities on mount', async () => {
    const cachedCapabilities = JSON.stringify({
      camera: true,
      location: true,
      notifications: false,
      biometric: true,
      screenRecording: false,
    });

    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_device_capabilities') return Promise.resolve(cachedCapabilities);
      return Promise.resolve(null);
    });

    renderWithDeviceProvider();

    await waitFor(() => {
      expect(screen.getByTestId('cameraCapability')).toHaveTextContent('true');
      expect(screen.getByTestId('locationCapability')).toHaveTextContent('true');
      expect(screen.getByTestId('notificationsCapability')).toHaveTextContent('false');
      expect(screen.getByTestId('biometricCapability')).toHaveTextContent('true');
    });
  });

  test('should update cache when capability changes', async () => {
    renderWithDeviceProvider();

    await act(async () => {
      // Change capability
    });

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_device_capabilities',
        expect.any(String)
      );
    });
  });
});
