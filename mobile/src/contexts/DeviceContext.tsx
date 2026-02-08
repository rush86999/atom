/**
 * DeviceContext - Mobile Device Registration and Capabilities
 *
 * Manages device registration, capabilities, and state:
 * - Device registration with push notification token
 * - Capability management (camera, location, etc.)
 * - Device state tracking
 * - Permission handling
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Platform, Alert } from 'react-native';
import * as Device from 'expo-device';
import { useAuth } from './AuthContext';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Expo modules for permissions
import * as Camera from 'expo-camera';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import * as LocalAuthentication from 'expo-local-authentication';

// Types
interface DeviceCapabilities {
  camera: boolean;
  location: boolean;
  notifications: boolean;
  biometric: boolean;
  screenRecording: boolean;
}

interface DeviceState {
  deviceId: string | null;
  deviceToken: string | null;
  platform: 'ios' | 'android' | null;
  isRegistered: boolean;
  capabilities: DeviceCapabilities;
  lastSync: Date | null;
}

interface DeviceContextType {
  // State
  deviceState: DeviceState;

  // Methods
  registerDevice: (pushToken: string) => Promise<{ success: boolean; error?: string }>;
  updateDeviceToken: (newToken: string) => Promise<void>;
  requestCapability: (capability: keyof DeviceCapabilities) => Promise<boolean>;
  checkCapability: (capability: keyof DeviceCapabilities) => Promise<boolean>;
  syncDevice: () => Promise<{ success: boolean; error?: string }>;
  unregisterDevice: () => Promise<void>;
}

const DeviceContext = createContext<DeviceContextType | undefined>(undefined);

// Constants
const DEVICE_ID_KEY = 'atom_device_id';
const DEVICE_TOKEN_KEY = 'atom_device_token';
const DEVICE_REGISTERED_KEY = 'atom_device_registered';
const CAPABILITIES_KEY = 'atom_device_capabilities';
const LAST_SYNC_KEY = 'atom_last_sync';

// API Base URL
const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * DeviceProvider Component
 */
export const DeviceProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { isAuthenticated, user } = useAuth();

  const [deviceState, setDeviceState] = useState<DeviceState>({
    deviceId: null,
    deviceToken: null,
    platform: Platform.OS as 'ios' | 'android',
    isRegistered: false,
    capabilities: {
      camera: false,
      location: false,
      notifications: false,
      biometric: false,
      screenRecording: false,
    },
    lastSync: null,
  });

  /**
   * Initialize device state on mount
   */
  useEffect(() => {
    loadDeviceState();
  }, []);

  /**
   * Load device state from storage
   */
  const loadDeviceState = async () => {
    try {
      const [deviceId, deviceToken, isRegistered, capabilitiesStr, lastSyncStr] = await Promise.all([
        AsyncStorage.getItem(DEVICE_ID_KEY),
        AsyncStorage.getItem(DEVICE_TOKEN_KEY),
        AsyncStorage.getItem(DEVICE_REGISTERED_KEY),
        AsyncStorage.getItem(CAPABILITIES_KEY),
        AsyncStorage.getItem(LAST_SYNC_KEY),
      ]);

      const capabilities: DeviceCapabilities = capabilitiesStr
        ? JSON.parse(capabilitiesStr)
        : {
            camera: false,
            location: false,
            notifications: false,
            biometric: false,
            screenRecording: false,
          };

      setDeviceState({
        deviceId,
        deviceToken,
        platform: Platform.OS as 'ios' | 'android',
        isRegistered: isRegistered === 'true',
        capabilities,
        lastSync: lastSyncStr ? new Date(lastSyncStr) : null,
      });
    } catch (error) {
      console.error('Failed to load device state:', error);
    }
  };

  /**
   * Get device information for registration
   */
  const getDeviceInfo = async () => {
    try {
      return {
        model: Device.modelName || 'Unknown',
        os_version: Platform.Version as string,
        platform: Platform.OS,
        device_type: Device.deviceType,
        total_memory: Device.totalMemory || 0,
        supported_abi: Device.supportedAbis || [],
      };
    } catch (error) {
      console.error('Failed to get device info:', error);
      return {
        model: 'Unknown',
        os_version: Platform.Version as string,
        platform: Platform.OS,
      };
    }
  };

  /**
   * Register device with backend
   */
  const registerDevice = async (pushToken: string): Promise<{ success: boolean; error?: string }> => {
    try {
      if (!isAuthenticated || !user) {
        return { success: false, error: 'Not authenticated' };
      }

      const deviceInfo = await getDeviceInfo();

      // In a real implementation, you'd get the access token from AuthContext
      // For now, we'll assume it's stored
      const accessToken = await AsyncStorage.getItem('atom_access_token');

      if (!accessToken) {
        return { success: false, error: 'No access token' };
      }

      const response = await fetch(`${API_BASE_URL}/api/mobile/notifications/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          device_token: pushToken,
          platform: Platform.OS,
          device_info: deviceInfo,
          notification_enabled: true,
          notification_preferences: {
            agent_alerts: true,
            system_alerts: true,
            workflow_updates: true,
          },
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || 'Registration failed' };
      }

      const data = await response.json();

      // Store device state
      const newDeviceId = data.device_id;
      await Promise.all([
        AsyncStorage.setItem(DEVICE_ID_KEY, newDeviceId),
        AsyncStorage.setItem(DEVICE_TOKEN_KEY, pushToken),
        AsyncStorage.setItem(DEVICE_REGISTERED_KEY, 'true'),
        AsyncStorage.setItem(LAST_SYNC_KEY, new Date().toISOString()),
      ]);

      setDeviceState((prev) => ({
        ...prev,
        deviceId: newDeviceId,
        deviceToken: pushToken,
        isRegistered: true,
        lastSync: new Date(),
      }));

      return { success: true };
    } catch (error: any) {
      console.error('Device registration error:', error);
      return { success: false, error: error.message || 'Network error' };
    }
  };

  /**
   * Update device token (e.g., after push token refresh)
   */
  const updateDeviceToken = async (newToken: string) => {
    try {
      if (!deviceState.isRegistered) {
        console.warn('Device not registered, cannot update token');
        return;
      }

      // In a real implementation, you'd call an API to update the token
      await AsyncStorage.setItem(DEVICE_TOKEN_KEY, newToken);

      setDeviceState((prev) => ({
        ...prev,
        deviceToken: newToken,
      }));
    } catch (error) {
      console.error('Failed to update device token:', error);
    }
  };

  /**
   * Request permission for a capability
   */
  const requestCapability = async (capability: keyof DeviceCapabilities): Promise<boolean> => {
    try {
      let granted = false;

      switch (capability) {
        case 'camera': {
          const { status } = await Camera.requestCameraPermissionsAsync();
          granted = status === 'granted';
          if (!granted) {
            Alert.alert(
              'Camera Permission Required',
              'Camera access is needed for this feature. Please enable it in your device settings.',
              [{ text: 'OK' }]
            );
          }
          break;
        }

        case 'location': {
          const { status } = await Location.requestForegroundPermissionsAsync();
          granted = status === 'granted';
          if (!granted) {
            Alert.alert(
              'Location Permission Required',
              'Location access is needed for this feature. Please enable it in your device settings.',
              [{ text: 'OK' }]
            );
          }
          break;
        }

        case 'notifications': {
          const { status: existingStatus } = await Notifications.getPermissionsAsync();
          let finalStatus = existingStatus;

          if (existingStatus !== 'granted') {
            const { status } = await Notifications.requestPermissionsAsync();
            finalStatus = status;
          }

          granted = finalStatus === 'granted';
          if (!granted) {
            Alert.alert(
              'Notification Permission Required',
              'Notifications are needed for this feature. Please enable them in your device settings.',
              [{ text: 'OK' }]
            );
          }
          break;
        }

        case 'biometric': {
          // Check if biometric authentication is available
          const compatible = await LocalAuthentication.hasHardwareAsync();
          if (!compatible) {
            Alert.alert(
              'Biometric Not Available',
              'This device does not support biometric authentication.',
              [{ text: 'OK' }]
            );
            granted = false;
            break;
          }

          const enrolled = await LocalAuthentication.isEnrolledAsync();
          if (!enrolled) {
            Alert.alert(
              'No Biometric Enrolled',
              'Please enroll a fingerprint or face ID in your device settings.',
              [{ text: 'OK' }]
            );
            granted = false;
            break;
          }

          // Attempt authentication
          const result = await LocalAuthentication.authenticateAsync({
            promptMessage: 'Authenticate to access this feature',
            fallbackLabel: 'Use password',
          });

          granted = result.success;
          if (!granted) {
            // User cancelled or authentication failed
            console.log('Biometric authentication failed or was cancelled');
          }
          break;
        }

        case 'screenRecording':
          // Screen recording is not supported on mobile
          granted = false;
          Alert.alert(
            'Feature Not Available',
            'Screen recording is not available on mobile devices.',
            [{ text: 'OK' }]
          );
          break;

        default:
          granted = false;
      }

      // Update capabilities
      const updatedCapabilities = { ...deviceState.capabilities, [capability]: granted };
      await AsyncStorage.setItem(CAPABILITIES_KEY, JSON.stringify(updatedCapabilities));

      setDeviceState((prev) => ({
        ...prev,
        capabilities: updatedCapabilities,
      }));

      return granted;
    } catch (error) {
      console.error(`Failed to request ${capability} capability:`, error);
      Alert.alert(
        'Permission Error',
        `Failed to request permission for ${capability}. Please try again.`,
        [{ text: 'OK' }]
      );
      return false;
    }
  };

  /**
   * Check if capability is granted
   */
  const checkCapability = async (capability: keyof DeviceCapabilities): Promise<boolean> => {
    try {
      switch (capability) {
        case 'camera': {
          const { status } = await Camera.getCameraPermissionsAsync();
          return status === 'granted';
        }

        case 'location': {
          const { status } = await Location.getForegroundPermissionsAsync();
          return status === 'granted';
        }

        case 'notifications': {
          const { status } = await Notifications.getPermissionsAsync();
          return status === 'granted';
        }

        case 'biometric': {
          const compatible = await LocalAuthentication.hasHardwareAsync();
          const enrolled = await LocalAuthentication.isEnrolledAsync();
          return compatible && enrolled;
        }

        case 'screenRecording':
          // Screen recording is not supported on mobile
          return false;

        default:
          return false;
      }
    } catch (error) {
      console.error(`Failed to check ${capability} capability:`, error);
      return false;
    }
  };

  /**
   * Sync device state with backend
   */
  const syncDevice = async (): Promise<{ success: boolean; error?: string }> => {
    try {
      if (!deviceState.isRegistered) {
        return { success: false, error: 'Device not registered' };
      }

      const accessToken = await AsyncStorage.getItem('atom_access_token');

      if (!accessToken) {
        return { success: false, error: 'Not authenticated' };
      }

      // Trigger sync
      const response = await fetch(`${API_BASE_URL}/api/mobile/sync/trigger`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          device_id: deviceState.deviceId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        return { success: false, error: errorData.detail || 'Sync failed' };
      }

      const data = await response.json();

      // Update last sync time
      await AsyncStorage.setItem(LAST_SYNC_KEY, new Date().toISOString());

      setDeviceState((prev) => ({
        ...prev,
        lastSync: new Date(),
      }));

      return { success: true };
    } catch (error: any) {
      console.error('Device sync error:', error);
      return { success: false, error: error.message || 'Network error' };
    }
  };

  /**
   * Unregister device
   */
  const unregisterDevice = async () => {
    try {
      if (!deviceState.isRegistered) {
        return;
      }

      const accessToken = await AsyncStorage.getItem('atom_access_token');

      if (accessToken) {
        await fetch(`${API_BASE_URL}/api/mobile/notifications/unregister`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            device_id: deviceState.deviceId,
          }),
        });
      }

      // Clear device state
      await Promise.all([
        AsyncStorage.removeItem(DEVICE_ID_KEY),
        AsyncStorage.removeItem(DEVICE_TOKEN_KEY),
        AsyncStorage.removeItem(DEVICE_REGISTERED_KEY),
        AsyncStorage.removeItem(LAST_SYNC_KEY),
      ]);

      setDeviceState((prev) => ({
        ...prev,
        deviceId: null,
        deviceToken: null,
        isRegistered: false,
        lastSync: null,
      }));
    } catch (error) {
      console.error('Failed to unregister device:', error);
    }
  };

  const value: DeviceContextType = {
    deviceState,
    registerDevice,
    updateDeviceToken,
    requestCapability,
    checkCapability,
    syncDevice,
    unregisterDevice,
  };

  return <DeviceContext.Provider value={value}>{children}</DeviceContext.Provider>;
};

/**
 * useDevice Hook
 */
export const useDevice = (): DeviceContextType => {
  const context = useContext(DeviceContext);
  if (!context) {
    throw new Error('useDevice must be used within a DeviceProvider');
  }
  return context;
};
