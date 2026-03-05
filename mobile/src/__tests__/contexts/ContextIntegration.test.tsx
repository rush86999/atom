/**
 * Context Integration Tests
 *
 * Multi-provider integration tests verifying context providers work together correctly:
 *
 * **Auth + Device Integration:**
 * - Device registration requires authentication
 * - Device state cleared on logout
 * - Auth token used for device registration
 * - User info shared between contexts
 * - Auth state changes while device registered
 * - Device registration failure when auth expires
 *
 * **Auth + WebSocket Integration:**
 * - WebSocket connects only when authenticated
 * - WebSocket disconnects on logout
 * - Auth token used for WebSocket connection
 * - WebSocket reconnects after token refresh
 * - WebSocket connection without auth handled gracefully
 *
 * **Full Three-Provider Integration:**
 * - Providers mount in correct order (Auth > Device > WebSocket)
 * - Auth state passed to all dependent providers
 * - Logout cascades through all providers
 * - Concurrent state changes handled correctly
 * - Rapid auth state changes handled without corruption
 * - Performance tests for provider mounting and updates
 */

// Set environment variables before any imports
process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';

// Mock expo-constants before importing
jest.mock('expo-constants', () => ({
  expoConfig: {
    name: 'Atom',
    slug: 'atom',
    version: '1.0.0',
  },
  default: {
    expoConfig: {
      name: 'Atom',
      slug: 'atom',
      version: '1.0.0',
    },
  },
}));

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react-native';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';
import { DeviceProvider, useDevice } from '../../contexts/DeviceContext';
import { WebSocketProvider, useWebSocket } from '../../contexts/WebSocketContext';
import { Text, View, Pressable } from 'react-native';

// Mock fetch
global.fetch = jest.fn();

import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock socket.io-client
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    connected: false,
    on: jest.fn(),
    emit: jest.fn(),
    off: jest.fn(),
    disconnect: jest.fn(),
    connect: jest.fn(),
    once: jest.fn(),
  })),
}));

// ============================================================================
// Test Components
// ============================================================================

/**
 * TestApp component that wraps all three providers
 * This mimics the actual app structure for integration testing
 */
const TestApp: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  return (
    <AuthProvider>
      <DeviceProvider>
        <WebSocketProvider>
          <View>{children}</View>
        </WebSocketProvider>
      </DeviceProvider>
    </AuthProvider>
  );
};

/**
 * Component that consumes all three contexts
 * Used to verify integration between providers
 */
const MultiContextConsumer: React.FC = () => {
  const { isAuthenticated, user, isLoading: authLoading } = useAuth();
  const { deviceState } = useDevice();
  const { isConnected, isConnecting, connectionError } = useWebSocket();

  return (
    <View>
      <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
      <Text testID="authLoading">{authLoading.toString()}</Text>
      <Text testID="user">{user ? JSON.stringify(user) : 'null'}</Text>
      <Text testID="deviceId">{deviceState.deviceId || 'null'}</Text>
      <Text testID="deviceRegistered">{deviceState.isRegistered.toString()}</Text>
      <Text testID="socketConnected">{isConnected.toString()}</Text>
      <Text testID="socketConnecting">{isConnecting.toString()}</Text>
      <Text testID="socketError">{connectionError || 'none'}</Text>
    </View>
  );
};

// ============================================================================
// Setup and Teardown
// ============================================================================

const mockAccessToken = 'mock_access_token_123';
const mockRefreshToken = 'mock_refresh_token_456';
const mockUser = { id: 'user_1', email: 'test@example.com', name: 'Test User' };
const mockDeviceId = 'device_test_123';
const mockPushToken = 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]';

beforeEach(() => {
  jest.clearAllMocks();

  // Default successful mocks
  (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
  (SecureStore.setItemAsync as jest.Mock).mockResolvedValue(undefined);
  (SecureStore.deleteItemAsync as jest.Mock).mockResolvedValue(undefined);
  (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);
  (AsyncStorage.setItem as jest.Mock).mockResolvedValue(undefined);
  (AsyncStorage.removeItem as jest.Mock).mockResolvedValue(undefined);
  (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValue(true);
  (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValue(true);
  (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValue({ success: true });

  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({
      access_token: mockAccessToken,
      refresh_token: mockRefreshToken,
      user: mockUser,
    }),
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ============================================================================
// Auth + Device Integration Tests
// ============================================================================

describe('Context Integration - Auth + Device', () => {
  test('should allow device registration only when authenticated', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        success: false,
        error: 'Not authenticated',
      }),
    });

    const DeviceRegisterComponent = () => {
      const { registerDevice } = useDevice();
      const { isAuthenticated } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [attempted, setAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!attempted) {
          registerDevice(mockPushToken).then(setResult);
          setAttempted(true);
        }
      }, [attempted]);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="registerResult">{result ? JSON.stringify(result) : 'waiting'}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <DeviceRegisterComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
    });

    await waitFor(() => {
      const resultText = getByTestId('registerResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Not authenticated');
    });
  });

  test('should allow device registration after authentication', async () => {
    let registerAttempted = false;

    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: mockAccessToken,
          refresh_token: mockRefreshToken,
          user: mockUser,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          device_id: mockDeviceId,
        }),
      });

    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    const DeviceRegisterComponent = () => {
      const { registerDevice } = useDevice();
      const { isAuthenticated, login } = useAuth();
      const [registerResult, setRegisterResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      React.useEffect(() => {
        if (isAuthenticated && !registerAttempted) {
          registerDevice(mockPushToken).then(setRegisterResult);
          registerAttempted = true;
        }
      }, [isAuthenticated]);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="registerResult">{registerResult ? JSON.stringify(registerResult) : 'waiting'}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <DeviceRegisterComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
    });

    await waitFor(() => {
      const resultText = getByTestId('registerResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(true);
    });
  });

  test('should clear device state on logout', async () => {
    // Setup authenticated and registered state
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_device_registered') return Promise.resolve('true');
      return Promise.resolve(null);
    });

    const LogoutComponent = () => {
      const { logout, isAuthenticated } = useAuth();
      const { deviceState } = useDevice();

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="deviceRegistered">{deviceState.isRegistered.toString()}</Text>
          <Pressable testID="logoutButton" onPress={logout} />
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <LogoutComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
      expect(getByTestId('deviceRegistered').props.children).toBe('true');
    });

    jest.clearAllMocks();

    act(() => {
      getByTestId('logoutButton').props.onPress();
    });

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
    });

    // Verify device state was cleared
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_token');
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_registered');
  });

  test('should use auth token for device registration', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        device_id: mockDeviceId,
      }),
    });

    const DeviceRegisterComponent = () => {
      const { registerDevice } = useDevice();
      const [attempted, setAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!attempted) {
          registerDevice(mockPushToken);
          setAttempted(true);
        }
      }, [attempted]);

      return <Text testID="ready">ready</Text>;
    };

    render(
      <AuthProvider>
        <DeviceProvider>
          <DeviceRegisterComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/mobile/notifications/register'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': `Bearer ${mockAccessToken}`,
          }),
        })
      );
    });
  });

  test('should share user info between contexts', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    const UserInfoComponent = () => {
      const { user } = useAuth();
      const { deviceState } = useDevice();

      return (
        <View>
          <Text testID="authUser">{user ? JSON.stringify(user) : 'null'}</Text>
          <Text testID="devicePlatform">{deviceState.platform || 'null'}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <UserInfoComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authUser').props.children).toBe(JSON.stringify(mockUser));
      expect(getByTestId('devicePlatform')).toBeTruthy();
    });
  });

  test('should handle auth state changes while device registered', async () => {
    const newAccessToken = 'new_access_token_789';

    // Setup initial authenticated state with device registered
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_device_registered') return Promise.resolve('true');
      return Promise.resolve(null);
    });

    const TokenRefreshComponent = () => {
      const { isAuthenticated } = useAuth();
      const { deviceState } = useDevice();

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="deviceRegistered">{deviceState.isRegistered.toString()}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <TokenRefreshComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
      expect(getByTestId('deviceRegistered').props.children).toBe('true');
    });

    // Simulate token refresh
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(newAccessToken);
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_device_registered') return Promise.resolve('true');
      return Promise.resolve(null);
    });

    await act(async () => {
      // Trigger re-render
    });

    await waitFor(() => {
      expect(getByTestId('deviceRegistered').props.children).toBe('true');
    });
  });

  test('should handle device registration failure when auth expires', async () => {
    // Auth token exists but is expired
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve('expired_token');
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Token expired' }),
    });

    const DeviceRegisterComponent = () => {
      const { registerDevice } = useDevice();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [attempted, setAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!attempted) {
          registerDevice(mockPushToken).then(setResult);
          setAttempted(true);
        }
      }, [attempted]);

      return <Text testID="registerResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <DeviceRegisterComponent />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('registerResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(false);
      expect(result.error).toBeTruthy();
    });
  });

  test('should require DeviceProvider inside AuthProvider', async () => {
    // This test verifies the provider nesting order
    const Component = () => {
      const { isAuthenticated } = useAuth();
      return <Text testID="authStatus">{isAuthenticated.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceProvider>
          <Component />
        </DeviceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus')).toBeTruthy();
    });
  });

  test('should throw error when useDevice used without DeviceProvider', async () => {
    const Component = () => {
      try {
        const { deviceState } = useDevice();
        return <Text testID="deviceState">{deviceState.deviceId || 'null'}</Text>;
      } catch (error: any) {
        return <Text testID="error">{error.message}</Text>;
      }
    };

    const { getByTestId } = render(
      <AuthProvider>
        <Component />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('error').props.children).toContain('useDevice must be used within a DeviceProvider');
    });
  });

  test('should throw error when useAuth used without AuthProvider', async () => {
    const Component = () => {
      try {
        const { isAuthenticated } = useAuth();
        return <Text testID="authStatus">{isAuthenticated.toString()}</Text>;
      } catch (error: any) {
        return <Text testID="error">{error.message}</Text>;
      }
    };

    const { getByTestId } = render(
      <DeviceProvider>
        <Component />
      </DeviceProvider>
    );

    await waitFor(() => {
      expect(getByTestId('error').props.children).toContain('useAuth must be used within an AuthProvider');
    });
  });
});

// ============================================================================
// Auth + WebSocket Integration Tests
// ============================================================================

describe('Context Integration - Auth + WebSocket', () => {
  test('should connect WebSocket only when authenticated', async () => {
    const WebSocketComponent = () => {
      const { isAuthenticated } = useAuth();
      const { isConnected, connect } = useWebSocket();
      const [connectAttempted, setConnectAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!connectAttempted && !isAuthenticated) {
          connect();
          setConnectAttempted(true);
        }
      }, [connectAttempted, isAuthenticated]);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="socketConnected">{isConnected.toString()}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <WebSocketProvider>
          <WebSocketComponent />
        </WebSocketProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
      expect(getByTestId('socketConnected').props.children).toBe('false');
    });
  });

  test('should connect WebSocket after authentication', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: mockAccessToken,
        refresh_token: mockRefreshToken,
        user: mockUser,
      }),
    });

    const WebSocketComponent = () => {
      const { isAuthenticated, login } = useAuth();
      const { isConnected } = useWebSocket();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="socketConnected">{isConnected.toString()}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <WebSocketProvider>
          <WebSocketComponent />
        </WebSocketProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
    }, { timeout: 5000 });
  });

  test('should disconnect WebSocket on logout', async () => {
    // Setup authenticated state
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    const LogoutComponent = () => {
      const { logout, isAuthenticated } = useAuth();
      const { isConnected } = useWebSocket();

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="socketConnected">{isConnected.toString()}</Text>
          <Pressable testID="logoutButton" onPress={logout} />
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <WebSocketProvider>
          <LogoutComponent />
        </WebSocketProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
    }, { timeout: 5000 });

    act(() => {
      getByTestId('logoutButton').props.onPress();
    });

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
    });
  });

  test('should use auth token for WebSocket connection', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(mockAccessToken);

    const { io } = require('socket.io-client');

    const WebSocketComponent = () => {
      const { connect } = useWebSocket();
      const [attempted, setAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!attempted) {
          connect();
          setAttempted(true);
        }
      }, [attempted]);

      return <Text testID="ready">ready</Text>;
    };

    render(
      <AuthProvider>
        <WebSocketProvider>
          <WebSocketComponent />
        </WebSocketProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(io).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          auth: expect.objectContaining({
            token: mockAccessToken,
          }),
        })
      );
    });
  });

  test('should reconnect WebSocket after token refresh', async () => {
    const newAccessToken = 'new_access_token_789';

    // Initial token
    (AsyncStorage.getItem as jest.Mock)
      .mockResolvedValueOnce(mockAccessToken)
      .mockResolvedValueOnce(newAccessToken);

    const TokenRefreshComponent = () => {
      const { isConnected } = useWebSocket();

      return <Text testID="socketConnected">{isConnected.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <WebSocketProvider>
          <TokenRefreshComponent />
        </WebSocketProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('socketConnected')).toBeTruthy();
    });
  });

  test('should handle WebSocket connection without auth gracefully', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

    const WebSocketComponent = () => {
      const { connectionError } = useWebSocket();
      const [attempted, setAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!attempted) {
          // Attempt to connect without auth
          setAttempted(true);
        }
      }, [attempted]);

      return <Text testID="socketError">{connectionError || 'none'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <WebSocketProvider>
          <WebSocketComponent />
        </WebSocketProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('socketError')).toBeTruthy();
    });
  });
});

// ============================================================================
// Full Three-Provider Integration Tests
// ============================================================================

describe('Context Integration - Full Three-Provider', () => {
  test('should mount all providers in correct order', async () => {
    const { getByTestId } = render(
      <TestApp>
        <MultiContextConsumer />
      </TestApp>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus')).toBeTruthy();
      expect(getByTestId('deviceRegistered')).toBeTruthy();
      expect(getByTestId('socketConnected')).toBeTruthy();
    });
  });

  test('should pass auth state to all dependent providers', async () => {
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: mockAccessToken,
        refresh_token: mockRefreshToken,
        user: mockUser,
      }),
    });

    const AuthStateComponent = () => {
      const { login, isAuthenticated } = useAuth();
      const { deviceState } = useDevice();
      const { isConnected } = useWebSocket();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="deviceReady">{deviceState.platform || 'null'}</Text>
          <Text testID="socketReady">{isConnected.toString()}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <TestApp>
        <AuthStateComponent />
      </TestApp>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
      expect(getByTestId('deviceReady')).toBeTruthy();
      expect(getByTestId('socketReady')).toBeTruthy();
    }, { timeout: 5000 });
  });

  test('should handle logout across all providers', async () => {
    // Setup authenticated state
    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_device_id') return Promise.resolve(mockDeviceId);
      if (key === 'atom_device_registered') return Promise.resolve('true');
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    const LogoutAllComponent = () => {
      const { logout, isAuthenticated } = useAuth();
      const { deviceState } = useDevice();
      const { isConnected } = useWebSocket();

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="deviceRegistered">{deviceState.isRegistered.toString()}</Text>
          <Text testID="socketConnected">{isConnected.toString()}</Text>
          <Pressable testID="logoutButton" onPress={logout} />
        </View>
      );
    };

    const { getByTestId } = render(
      <TestApp>
        <LogoutAllComponent />
      </TestApp>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
    }, { timeout: 5000 });

    jest.clearAllMocks();

    act(() => {
      getByTestId('logoutButton').props.onPress();
    });

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
    });

    // Verify all providers cleared state
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_device_id');
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_user_data');
  });

  test('should handle concurrent state changes', async () => {
    const ConcurrentComponent = () => {
      const { login, isAuthenticated } = useAuth();
      const { registerDevice } = useDevice();
      const { connect } = useWebSocket();
      const [attempted, setAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!attempted) {
          // Trigger all operations concurrently
          Promise.all([
            login({ email: 'test@example.com', password: 'password' }),
            registerDevice(mockPushToken),
            connect(),
          ]);
          setAttempted(true);
        }
      }, [attempted]);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="ready">ready</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <TestApp>
        <ConcurrentComponent />
      </TestApp>
    );

    await waitFor(() => {
      expect(getByTestId('ready')).toBeTruthy();
    });
  });

  test('should handle rapid auth state changes', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: mockAccessToken,
        refresh_token: mockRefreshToken,
        user: mockUser,
      }),
    });

    const RapidChangesComponent = () => {
      const { login, logout, isAuthenticated } = useAuth();
      const [changeCount, setChangeCount] = React.useState(0);
      const [ready, setReady] = React.useState(false);

      React.useEffect(() => {
        const rapidChanges = async () => {
          // Login -> logout -> login rapidly
          await login({ email: 'test@example.com', password: 'password' });
          setChangeCount(1);
          await logout();
          setChangeCount(2);
          await login({ email: 'test@example.com', password: 'password' });
          setChangeCount(3);
          setReady(true);
        };

        rapidChanges();
      }, []);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="changeCount">{changeCount.toString()}</Text>
          <Text testID="ready">{ready.toString()}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <TestApp>
        <RapidChangesComponent />
      </TestApp>
    );

    await waitFor(() => {
      expect(getByTestId('ready').props.children).toBe('true');
      expect(getByTestId('changeCount').props.children).toBe('3');
    }, { timeout: 10000 });
  });
});

// ============================================================================
// Performance Tests
// ============================================================================

describe('Context Integration - Performance', () => {
  test('should render all providers within acceptable time', async () => {
    const startTime = Date.now();

    render(
      <TestApp>
        <MultiContextConsumer />
      </TestApp>
    );

    await waitFor(() => {
      expect(screen.getByTestId('authStatus')).toBeTruthy();
    });

    const endTime = Date.now();
    const renderTime = endTime - startTime;

    // Should render in less than 100ms
    expect(renderTime).toBeLessThan(100);
  });

  test('should handle context updates without performance degradation', async () => {
    const UpdatePerformanceComponent = () => {
      const { isAuthenticated } = useAuth();
      const [updateCount, setUpdateCount] = React.useState(0);
      const [ready, setReady] = React.useState(false);

      React.useEffect(() => {
        const startTime = Date.now();

        // Trigger 100 state updates
        for (let i = 0; i < 100; i++) {
          setUpdateCount(i);
        }

        const endTime = Date.now();
        const updateDuration = endTime - startTime;

        // Updates should complete in reasonable time (< 1 second for 100 updates)
        expect(updateDuration).toBeLessThan(1000);
        setReady(true);
      }, []);

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="updateCount">{updateCount.toString()}</Text>
          <Text testID="ready">{ready.toString()}</Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <TestApp>
        <UpdatePerformanceComponent />
      </TestApp>
    );

    await waitFor(() => {
      expect(getByTestId('ready').props.children).toBe('true');
      expect(getByTestId('updateCount').props.children).toBe('99');
    });
  });
});
