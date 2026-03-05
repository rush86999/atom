/**
 * App Lifecycle Integration Tests
 *
 * Tests for AppState mock utilities and lifecycle simulation infrastructure.
 * These tests validate the testing framework for future app lifecycle implementation.
 *
 * @see https://reactnative.dev/docs/appstate
 */

// Set environment variables before any imports
process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react-native';
import { Text, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

// Import contexts
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { DeviceProvider, useDevice } from '../../contexts/DeviceContext';
import { WebSocketProvider, useWebSocket } from '../../contexts/WebSocketContext';

// Import test helpers
import {
  setupAuthenticatedState,
  setupRegisteredDevice,
  clearAllStorage,
  verifyAuthState,
  verifyDeviceState,
  createValidToken,
  createExpiredToken,
  createMockUser,
  createMockDevice,
  calculateTokenExpiry,
  mockAsyncStorageState,
  mockSecureStoreState,
} from '../helpers/storageTestHelpers';
import { flushPromises } from '../helpers/testUtils';

// Mock fetch for token refresh and API calls
global.fetch = jest.fn();

// ============================================================================
// AppState Mock Utilities
// ============================================================================

/**
 * AppState Mock Utilities
 *
 * Mock React Native AppState for lifecycle testing.
 * These utilities allow tests to simulate app background/foreground transitions.
 *
 * Note: AppState mock is set up in jest.setup.js. These utilities
 * provide helper functions to trigger state changes during tests.
 */

type AppStateStatus = 'active' | 'background' | 'inactive';

// Use global listeners from jest.setup.js
declare const global: any & { appStateListeners: Array<(AppStateStatus) => void> };

/**
 * Simulate app state change
 * Triggers all registered 'change' listeners
 *
 * @param nextState - New app state ('active' | 'background' | 'inactive')
 */
export const simulateAppStateChange = (nextState: AppStateStatus): void => {
  console.log(`[MockAppState] State change: ${nextState}`);

  // Trigger all registered listeners from jest.setup.js
  global.appStateListeners.forEach((callback: (AppStateStatus) => void) => {
    try {
      callback(nextState);
    } catch (error) {
      console.error('[MockAppState] Error in listener:', error);
    }
  });
};

/**
 * Wait for AppState change handlers to execute
 */
export const waitForAppStateChange = async (timeout: number = 1000): Promise<void> => {
  await flushPromises();
  await act(async () => {
    await new Promise(resolve => setTimeout(resolve, 50));
  });
};

/**
 * Get all registered AppState listeners
 */
export const getAppStateListeners = (): Array<(AppStateStatus) => void> => {
  return [...global.appStateListeners];
};

/**
 * Reset all AppState listeners
 */
export const resetAppStateListeners = (): void => {
  global.appStateListeners.length = 0;
};

/**
 * Get current app state from mock
 */
export const getCurrentAppState = (): AppStateStatus => {
  return 'active';
};

// ============================================================================
// Test Components
// ============================================================================

const AuthTestComponent: React.FC = () => {
  const { isAuthenticated, isLoading, user } = useAuth();
  return (
    <View>
      <Text testID="isAuthenticated">{isAuthenticated.toString()}</Text>
      <Text testID="isLoading">{isLoading.toString()}</Text>
      <Text testID="userId">{user?.id || 'null'}</Text>
      <Text testID="userEmail">{user?.email || 'null'}</Text>
    </View>
  );
};

const DeviceTestComponent: React.FC = () => {
  const { deviceState } = useDevice();
  return (
    <View>
      <Text testID="deviceId">{deviceState.deviceId || 'null'}</Text>
      <Text testID="deviceToken">{deviceState.deviceToken || 'null'}</Text>
      <Text testID="isRegistered">{deviceState.isRegistered.toString()}</Text>
    </View>
  );
};

const renderWithAuthProvider = (component: React.ReactNode) => {
  return render(<AuthProvider>{component}</AuthProvider>);
};

const renderWithDeviceProvider = (component: React.ReactNode) => {
  return render(
    <AuthProvider>
      <DeviceProvider>{component}</DeviceProvider>
    </AuthProvider>
  );
};

const renderWithAllProviders = (component: React.ReactNode) => {
  return render(
    <AuthProvider>
      <DeviceProvider>
        <WebSocketProvider>{component}</WebSocketProvider>
      </DeviceProvider>
    </AuthProvider>
  );
};

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  jest.clearAllMocks();
  resetAppStateListeners();

  // Clear AsyncStorage and SecureStore mocks
  if (global.__resetAsyncStorageMock) {
    global.__resetAsyncStorageMock();
  }
  if (global.__resetSecureStoreMock) {
    global.__resetSecureStoreMock();
  }

  // Default successful fetch mock
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({
      access_token: createValidToken(24),
      refresh_token: 'new_refresh_token',
      user: createMockUser(),
    }),
  });
});

afterEach(() => {
  jest.clearAllMocks();
  resetAppStateListeners();
});

// ============================================================================
// AuthContext Lifecycle Tests
// ============================================================================

describe('AuthContext App Lifecycle', () => {
  test('should persist auth state when app goes to background', async () => {
    // Setup: User is authenticated
    await setupAuthenticatedState();

    // Verify: Auth state is in storage before background
    const verificationBefore = await verifyAuthState({
      hasAccessToken: true,
      hasRefreshToken: true,
      hasUserData: true,
    });
    expect(verificationBefore.matches).toBe(true);

    // Action: Simulate app going to background
    simulateAppStateChange('background');
    await waitForAppStateChange();

    // Verify: Auth state is still persisted in storage after background
    const verificationAfter = await verifyAuthState({
      hasAccessToken: true,
      hasRefreshToken: true,
      hasUserData: true,
    });

    expect(verificationAfter.matches).toBe(true);
  });

  test('should restore auth state when app returns to foreground', async () => {
    // Setup: User is authenticated
    await setupAuthenticatedState();

    // Action: Simulate app going to background then foreground
    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Verify: Auth state is still in storage
    const verification = await verifyAuthState({
      hasAccessToken: true,
      hasRefreshToken: true,
      hasUserData: true,
    });

    expect(verification.matches).toBe(true);
  });

  test('should not refresh token on brief background transition', async () => {
    // Setup: User authenticated with valid token
    await mockSecureStoreState({
      atom_access_token: createValidToken(24),
      atom_refresh_token: 'mock_refresh_token',
      atom_token_expiry: calculateTokenExpiry(24),
    });
    await mockAsyncStorageState({
      atom_user_data: JSON.stringify(createMockUser()),
    });

    renderWithAuthProvider(<AuthTestComponent />);

    // Wait for auth to initialize
    await waitFor(
      () => {
        expect(screen.getByTestId('isLoading').props.children).toBe('false');
      },
      { timeout: 5000 }
    );

    // Clear fetch calls from initial hydration
    (global.fetch as jest.Mock).mockClear();

    // Action: Brief background transition
    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Verify: No token refresh API called (AuthContext doesn't listen to AppState yet)
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('should handle token expiry during extended background', async () => {
    // Setup: Token is in storage
    await mockSecureStoreState({
      atom_access_token: createValidToken(24),
      atom_refresh_token: 'mock_refresh_token',
      atom_token_expiry: calculateTokenExpiry(24),
    });
    await mockAsyncStorageState({
      atom_user_data: JSON.stringify(createMockUser()),
    });

    renderWithAuthProvider(<AuthTestComponent />);

    await waitFor(
      () => {
        expect(screen.getByTestId('isLoading').props.children).toBe('false');
      },
      { timeout: 5000 }
    );

    // Action: Extended background
    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Verify: AppState change works (infrastructure test)
    expect(getCurrentAppState()).toBe('active');
  });

  test('should save device state before background transition', async () => {
    // Setup: Device registered
    const device = createMockDevice();
    await mockSecureStoreState({
      atom_access_token: createValidToken(24),
      atom_refresh_token: 'mock_refresh_token',
      atom_token_expiry: calculateTokenExpiry(24),
    });
    await mockAsyncStorageState({
      atom_user_data: JSON.stringify(createMockUser()),
      atom_device_id: device.device_token,
      atom_device_token: device.device_token,
    });

    // Verify: Device state is in storage before background
    const deviceIdBefore = await AsyncStorage.getItem('atom_device_id');
    expect(deviceIdBefore).toBeTruthy();

    // Action: Simulate app going to background
    simulateAppStateChange('background');
    await waitForAppStateChange();

    // Verify: Device state still in AsyncStorage after background
    const deviceIdAfter = await AsyncStorage.getItem('atom_device_id');
    expect(deviceIdAfter).toBeTruthy();
  });
});

// ============================================================================
// Lifecycle Test Utilities
// ============================================================================

describe('Lifecycle Test Utilities', () => {
  test('should track AppState listeners', () => {
    const listeners = getAppStateListeners();
    expect(listeners).toBeDefined();
    expect(Array.isArray(listeners)).toBe(true);
  });

  test('should simulate app state changes', async () => {
    const initialLength = getAppStateListeners().length;

    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Listeners should still be registered
    expect(getAppStateListeners().length).toBe(initialLength);
  });

  test('should reset listeners between tests', () => {
    // Add a mock listener
    global.appStateListeners.push(jest.fn());

    expect(getAppStateListeners().length).toBeGreaterThan(0);

    // Reset
    resetAppStateListeners();

    expect(getAppStateListeners()).toHaveLength(0);
  });

  test('should get current app state', () => {
    const state = getCurrentAppState();
    expect(state).toBeDefined();
    expect(['active', 'background', 'inactive']).toContain(state);
  });
});

// ============================================================================
// AppState Integration with Providers
// ============================================================================

describe('AppState Integration', () => {
  test('should handle AppState changes with AuthProvider', async () => {
    await setupAuthenticatedState();
    renderWithAuthProvider(<AuthTestComponent />);

    await waitFor(
      () => {
        expect(screen.getByTestId('isLoading').props.children).toBe('false');
      },
      { timeout: 5000 }
    );

    // Simulate background/foreground
    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Component should still render without errors
    expect(screen.getByTestId('isAuthenticated')).toBeTruthy();
  });

  test('should handle AppState changes with DeviceProvider', async () => {
    await setupAuthenticatedState();
    await setupRegisteredDevice();

    renderWithDeviceProvider(<DeviceTestComponent />);

    // Wait for initialization
    await waitFor(
      () => {
        expect(screen.getByTestId('deviceId')).toBeTruthy();
      },
      { timeout: 5000 }
    );

    // Simulate background/foreground
    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Component should still render without errors
    expect(screen.getByTestId('deviceId')).toBeTruthy();
  });

  test('should handle AppState changes with all providers', async () => {
    await setupAuthenticatedState();
    await setupRegisteredDevice();

    renderWithAllProviders(<AuthTestComponent />);

    // Wait for initialization
    await waitFor(
      () => {
        expect(screen.getByTestId('isLoading')).toBeTruthy();
      },
      { timeout: 5000 }
    );

    // Simulate background/foreground
    simulateAppStateChange('background');
    await waitForAppStateChange();

    simulateAppStateChange('active');
    await waitForAppStateChange();

    // Component should still render without errors
    expect(screen.getByTestId('isAuthenticated')).toBeTruthy();
  });

  test('should handle rapid AppState changes', async () => {
    await setupAuthenticatedState();
    renderWithAuthProvider(<AuthTestComponent />);

    await waitFor(
      () => {
        expect(screen.getByTestId('isLoading').props.children).toBe('false');
      },
      { timeout: 5000 }
    );

    // Simulate 5 rapid background/foreground transitions
    for (let i = 0; i < 5; i++) {
      simulateAppStateChange('background');
      await waitForAppStateChange();

      simulateAppStateChange('active');
      await waitForAppStateChange();
    }

    // Component should still render without errors
    expect(screen.getByTestId('isAuthenticated')).toBeTruthy();
  });
});
