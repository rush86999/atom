/**
 * DeviceContext Tests - Comprehensive Coverage
 *
 * Target: 80%+ coverage for DeviceContext.tsx
 */

import React from 'react';
import { render, waitFor, act, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import { DeviceProvider, useDevice } from '../DeviceContext';
import { AuthProvider } from '../AuthContext';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Camera from 'expo-camera';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import * as LocalAuthentication from 'expo-local-authentication';
import { Alert } from 'react-native';

// Mocks
global.fetch = jest.fn();

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
}));

jest.mock('expo-constants', () => ({
  expoConfig: {
    extra: {
      apiUrl: 'http://localhost:8000',
    },
  },
}));

jest.spyOn(Alert, 'alert').mockImplementation(() => {});

// Test component
const TestComponent = () => {
  const { deviceState } = useDevice();
  return (
    <>
      <Text testID="device-id">{deviceState.deviceId || 'null'}</Text>
      <Text testID="device-token">{deviceState.deviceToken || 'null'}</Text>
      <Text testID="is-registered">{deviceState.isRegistered.toString()}</Text>
      <Text testID="camera-cap">{deviceState.capabilities.camera.toString()}</Text>
      <Text testID="location-cap">{deviceState.capabilities.location.toString()}</Text>
      <Text testID="last-sync">{deviceState.lastSync ? 'synced' : 'null'}</Text>
    </>
  );
};

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <AuthProvider>
      <DeviceProvider>
        <TestComponent />
        {component}
      </DeviceProvider>
    </AuthProvider>
  );
};

// Constants
const MOCK_DEVICE_ID = 'test-device-123';
const MOCK_PUSH_TOKEN = 'ExponentPushToken[xxx]';
const MOCK_ACCESS_TOKEN = 'test-access-token';

// Setup
beforeEach(() => {
  jest.clearAllMocks();

  (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
  (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
  (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);

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
  (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
    success: true,
  });

  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({ device_id: MOCK_DEVICE_ID }),
  });
});

describe('DeviceContext', () => {
  describe('Initialization', () => {
    test('should initialize with default state', async () => {
      renderWithProviders(<></>);

      await waitFor(() => {
        expect(screen.getByTestId('is-registered').props.children).toBe('false');
        expect(screen.getByTestId('device-id').props.children).toBe('null');
      });
    });

    test('should load state from storage', async () => {
      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_id') return Promise.resolve('stored-id');
        if (key === 'atom_device_registered') return Promise.resolve('true');
        return Promise.resolve(null);
      });

      renderWithProviders(<></>);

      await waitFor(() => {
        expect(screen.getByTestId('device-id').props.children).toBe('stored-id');
        expect(screen.getByTestId('is-registered').props.children).toBe('true');
      });
    });

    test('should handle storage errors', async () => {
      (AsyncStorage.getItem as jest.Mock).mockRejectedValue(new Error('Error'));
      const spy = jest.spyOn(console, 'error').mockImplementation();

      renderWithProviders(<></>);

      await waitFor(() => {
        expect(spy).toHaveBeenCalledWith('Failed to load device state:', expect.any(Error));
      });

      spy.mockRestore();
    });
  });

  describe('Device Registration', () => {
    test('should register device successfully', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.registerDevice(MOCK_PUSH_TOKEN);
        expect(result.success).toBe(true);
      });

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/mobile/notifications/register',
        expect.objectContaining({
          method: 'POST',
        })
      );

      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_id', MOCK_DEVICE_ID);
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_token', MOCK_PUSH_TOKEN);
      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_registered', 'true');
    });

    test('should fail when not authenticated', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.registerDevice(MOCK_PUSH_TOKEN);
        expect(result.success).toBe(false);
        expect(result.error).toBe('Not authenticated');
      });
    });

    test('should fail when no access token', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_access_token') return Promise.resolve(null);
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.registerDevice(MOCK_PUSH_TOKEN);
        expect(result.success).toBe(false);
        expect(result.error).toBe('No access token');
      });
    });

    test('should handle API error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'API Error' }),
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.registerDevice(MOCK_PUSH_TOKEN);
        expect(result.success).toBe(false);
        expect(result.error).toBe('API Error');
      });
    });

    test('should handle network error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.registerDevice(MOCK_PUSH_TOKEN);
        expect(result.success).toBe(false);
        expect(result.error).toBe('Network error');
      });
    });
  });

  describe('Update Device Token', () => {
    test('should update token when registered', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.updateDeviceToken('new-token');
      });

      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_token', 'new-token');
    });

    test('should not update token when not registered', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      const spy = jest.spyOn(console, 'warn').mockImplementation();

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.updateDeviceToken('new-token');
      });

      expect(spy).toHaveBeenCalledWith('Device not registered, cannot update token');
      spy.mockRestore();
    });

    test('should handle update error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        return Promise.resolve(null);
      });

      (AsyncStorage.setItem as jest.Mock).mockRejectedValue(new Error('Error'));
      const spy = jest.spyOn(console, 'error').mockImplementation();

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.updateDeviceToken('new-token');
      });

      expect(spy).toHaveBeenCalledWith('Failed to update device token:', expect.any(Error));
      spy.mockRestore();
    });
  });

  describe('Request Capability', () => {
    test('should request camera permission', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('camera');
        expect(granted).toBe(true);
      });

      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_device_capabilities',
        expect.stringContaining('"camera":true')
      );
    });

    test('should handle camera denied', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('camera');
        expect(granted).toBe(false);
      });

      expect(Alert.alert).toHaveBeenCalled();
    });

    test('should request location permission', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('location');
        expect(granted).toBe(true);
      });

      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalled();
    });

    test('should handle location denied', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('location');
        expect(granted).toBe(false);
      });

      expect(Alert.alert).toHaveBeenCalled();
    });

    test('should request notifications permission', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'undetermined',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('notifications');
        expect(granted).toBe(true);
      });

      expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();
    });

    test('should request biometric permission', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('biometric');
        expect(granted).toBe(true);
      });

      expect(LocalAuthentication.authenticateAsync).toHaveBeenCalled();
    });

    test('should handle biometric not available', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(false);

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('biometric');
        expect(granted).toBe(false);
      });

      expect(Alert.alert).toHaveBeenCalledWith(
        'Biometric Not Available',
        expect.any(String),
        expect.any(Array)
      );
    });

    test('should handle no biometric enrolled', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
      (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(false);

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('biometric');
        expect(granted).toBe(false);
      });

      expect(Alert.alert).toHaveBeenCalledWith(
        'No Biometric Enrolled',
        expect.any(String),
        expect.any(Array)
      );
    });

    test('should handle biometric auth failure', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({
        success: false,
      });

      const spy = jest.spyOn(console, 'log').mockImplementation();

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('biometric');
        expect(granted).toBe(false);
      });

      expect(spy).toHaveBeenCalledWith('Biometric authentication failed or was cancelled');
      spy.mockRestore();
    });

    test('should handle screen recording unavailable', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('screenRecording');
        expect(granted).toBe(false);
      });

      expect(Alert.alert).toHaveBeenCalledWith(
        'Feature Not Available',
        expect.any(String),
        expect.any(Array)
      );
    });

    test('should handle capability request error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (Camera.requestCameraPermissionsAsync as jest.Mock).mockRejectedValue(new Error('Error'));
      const spy = jest.spyOn(console, 'error').mockImplementation();

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const granted = await contextValue.requestCapability('camera');
        expect(granted).toBe(false);
      });

      expect(spy).toHaveBeenCalledWith('Failed to request camera capability:', expect.any(Error));
      expect(Alert.alert).toHaveBeenCalledWith(
        'Permission Error',
        expect.any(String),
        expect.any(Array)
      );
      spy.mockRestore();
    });
  });

  describe('Check Capability', () => {
    test('should check camera', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const has = await contextValue.checkCapability('camera');
        expect(has).toBe(true);
      });

      expect(Camera.getCameraPermissionsAsync).toHaveBeenCalled();
    });

    test('should check location', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const has = await contextValue.checkCapability('location');
        expect(has).toBe(true);
      });

      expect(Location.getForegroundPermissionsAsync).toHaveBeenCalled();
    });

    test('should check notifications', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const has = await contextValue.checkCapability('notifications');
        expect(has).toBe(true);
      });

      expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
    });

    test('should check biometric', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const has = await contextValue.checkCapability('biometric');
        expect(has).toBe(true);
      });

      expect(LocalAuthentication.hasHardwareAsync).toHaveBeenCalled();
      expect(LocalAuthentication.isEnrolledAsync).toHaveBeenCalled();
    });

    test('should return false for screen recording', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const has = await contextValue.checkCapability('screenRecording');
        expect(has).toBe(false);
      });
    });

    test('should handle check error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (Camera.getCameraPermissionsAsync as jest.Mock).mockRejectedValue(new Error('Error'));
      const spy = jest.spyOn(console, 'error').mockImplementation();

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const has = await contextValue.checkCapability('camera');
        expect(has).toBe(false);
      });

      expect(spy).toHaveBeenCalledWith('Failed to check camera capability:', expect.any(Error));
      spy.mockRestore();
    });
  });

  describe('Device Sync', () => {
    test('should sync device successfully', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.syncDevice();
        expect(result.success).toBe(true);
      });

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/mobile/sync/trigger',
        expect.objectContaining({
          method: 'POST',
        })
      );

      expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_last_sync', expect.any(String));
    });

    test('should fail sync when not registered', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.syncDevice();
        expect(result.success).toBe(false);
        expect(result.error).toBe('Device not registered');
      });
    });

    test('should fail sync when not authenticated', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.syncDevice();
        expect(result.success).toBe(false);
        expect(result.error).toBe('Not authenticated');
      });
    });

    test('should handle sync API error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Sync error' }),
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.syncDevice();
        expect(result.success).toBe(false);
        expect(result.error).toBe('Sync error');
      });
    });

    test('should handle sync network error', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        const result = await contextValue.syncDevice();
        expect(result.success).toBe(false);
        expect(result.error).toBe('Network error');
      });
    });
  });

  describe('Device Unregister', () => {
    test('should unregister device successfully', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        if (key === 'atom_device_token') return Promise.resolve(MOCK_PUSH_TOKEN);
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.unregisterDevice();
      });

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/mobile/notifications/unregister',
        expect.objectContaining({
          method: 'DELETE',
        })
      );

      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_token');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_registered');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_last_sync');
    });

    test('should not call API when not registered', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.unregisterDevice();
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('should unregister without access token', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        return Promise.resolve(null);
      });

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.unregisterDevice();
      });

      // Should still clear storage
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_token');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_registered');
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_last_sync');
    });

    test('should handle unregister error gracefully', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
        if (key === 'atom_device_registered') return Promise.resolve('true');
        if (key === 'atom_device_id') return Promise.resolve(MOCK_DEVICE_ID);
        if (key === 'atom_access_token') return Promise.resolve(MOCK_ACCESS_TOKEN);
        return Promise.resolve(null);
      });

      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));
      const spy = jest.spyOn(console, 'error').mockImplementation();

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await act(async () => {
        await contextValue.unregisterDevice();
      });

      // Should still clear storage
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
      expect(spy).toHaveBeenCalledWith('Failed to unregister device:', expect.any(Error));
      spy.mockRestore();
    });
  });

  describe('useDevice Hook', () => {
    test('should throw error outside provider', () => {
      const Component = () => {
        useDevice();
        return null;
      };

      expect(() => {
        render(<Component />);
      }).toThrow('useDevice must be used within a DeviceProvider');
    });

    test('should provide all methods', async () => {
      let contextValue: any;

      const ContextCapture = () => {
        contextValue = useDevice();
        return null;
      };

      render(
        <AuthProvider>
          <DeviceProvider>
            <ContextCapture />
          </DeviceProvider>
        </AuthProvider>
      );

      await waitFor(() => {
        expect(contextValue.deviceState).toBeDefined();
        expect(contextValue.registerDevice).toBeDefined();
        expect(contextValue.updateDeviceToken).toBeDefined();
        expect(contextValue.requestCapability).toBeDefined();
        expect(contextValue.checkCapability).toBeDefined();
        expect(contextValue.syncDevice).toBeDefined();
        expect(contextValue.unregisterDevice).toBeDefined();
      });
    });
  });
});
