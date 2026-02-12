/**
 * AuthContext Tests
 *
 * Tests for authentication context provider including:
 * - Login flow with valid/invalid credentials
 * - Token storage in SecureStore (access token, refresh token)
 * - Biometric authentication (hasHardware, isEnrolled, authenticate success/failure)
 * - Token refresh before expiry
 * - Logout and token cleanup
 * - Authentication state persistence across app restarts
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
import { Text, View, Pressable } from 'react-native';

// Mock fetch
global.fetch = jest.fn();

import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ============================================================================
// Test Components
// ============================================================================

const TestComponent: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, user, isLoading } = useAuth();
  return (
    <View>
      <Text testID="isAuthenticated">{isAuthenticated.toString()}</Text>
      <Text testID="isLoading">{isLoading.toString()}</Text>
      <Text testID="user">{user ? JSON.stringify(user) : 'null'}</Text>
      {children}
    </View>
  );
};

const renderWithAuthProvider = (component?: React.ReactNode) => {
  return render(
    <AuthProvider>
      <TestComponent>{component}</TestComponent>
    </AuthProvider>
  );
};

// ============================================================================
// Setup and Teardown
// ============================================================================

const mockAccessToken = 'mock_access_token_123';
const mockRefreshToken = 'mock_refresh_token_456';
const mockUser = { id: 'user_1', email: 'test@example.com', name: 'Test User' };

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
// Login Flow Tests
// ============================================================================

describe('Login Flow', () => {
  test('should login successfully with valid credentials', async () => {
    const LoginComponent = () => {
      const { login, isAuthenticated } = useAuth();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
    }, { timeout: 5000 });

    // Verify API was called
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/mobile/login'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
        body: expect.stringContaining('test@example.com'),
      })
    );

    // Verify tokens were stored
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'atom_access_token',
      mockAccessToken
    );
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'atom_refresh_token',
      mockRefreshToken
    );
  });

  test('should return error for invalid credentials (401)', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid email or password' }),
    });

    const LoginComponent = () => {
      const { login, isAuthenticated } = useAuth();
      const [error, setError] = React.useState<string | null>(null);
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      const handleLogin = async () => {
        const result = await login({ email: 'test@example.com', password: 'wrong' });
        if (!result.success) {
          setError(result.error || 'Login failed');
        }
        setLoginAttempted(true);
      };

      React.useEffect(() => {
        if (!loginAttempted) {
          handleLogin();
        }
      }, [loginAttempted]);

      return (
        <>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Text testID="error">{error || 'no error'}</Text>
        </>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
      expect(getByTestId('error').props.children).toBe('Invalid email or password');
    });
  });

  test('should return error for rate limiting (429)', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Too many attempts' }),
    });

    const LoginComponent = () => {
      const { login } = useAuth();
      const [error, setError] = React.useState<string | null>(null);
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      const handleLogin = async () => {
        const result = await login({ email: 'test@example.com', password: 'password' });
        setError(result.error || 'no error');
        setLoginAttempted(true);
      };

      React.useEffect(() => {
        if (!loginAttempted) {
          handleLogin();
        }
      }, [loginAttempted]);

      return <Text testID="error">{error || 'no error'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('error').props.children).toBe('Too many login attempts');
    });
  });

  test('should handle network errors gracefully', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    const LoginComponent = () => {
      const { login } = useAuth();
      const [error, setError] = React.useState<string | null>(null);
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      const handleLogin = async () => {
        const result = await login({ email: 'test@example.com', password: 'password' });
        setError(result.error || 'no error');
        setLoginAttempted(true);
      };

      React.useEffect(() => {
        if (!loginAttempted) {
          handleLogin();
        }
      }, [loginAttempted]);

      return <Text testID="error">{error || 'no error'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('error').props.children).toBe('Network error');
    });
  });
});

// ============================================================================
// Token Storage Tests
// ============================================================================

describe('Token Storage', () => {
  test('should store access token in SecureStore on login', async () => {
    const LoginComponent = () => {
      const { login } = useAuth();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return <Text testID="ready">ready</Text>;
    };

    render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
        'atom_access_token',
        mockAccessToken
      );
    });
  });

  test('should store refresh token in SecureStore on login', async () => {
    const LoginComponent = () => {
      const { login } = useAuth();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return <Text testID="ready">ready</Text>;
    };

    render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
        'atom_refresh_token',
        mockRefreshToken
      );
    });
  });

  test('should store token expiry time in SecureStore', async () => {
    const LoginComponent = () => {
      const { login } = useAuth();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return <Text testID="ready">ready</Text>;
    };

    render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
        'atom_token_expiry',
        expect.any(String)
      );
    });

    const expiryCall = (SecureStore.setItemAsync as jest.Mock).mock.calls.find(
      call => call[0] === 'atom_token_expiry'
    );
    const expiryTime = parseInt(expiryCall![1], 10);
    const now = Date.now();
    const oneDayMs = 24 * 60 * 60 * 1000;

    expect(expiryTime).toBeGreaterThan(now);
    expect(expiryTime).toBeLessThanOrEqual(now + oneDayMs + 1000); // +1s tolerance
  });

  test('should store user data in AsyncStorage', async () => {
    const LoginComponent = () => {
      const { login } = useAuth();
      const [loginAttempted, setLoginAttempted] = React.useState(false);

      React.useEffect(() => {
        if (!loginAttempted) {
          login({ email: 'test@example.com', password: 'password' });
          setLoginAttempted(true);
        }
      }, [loginAttempted]);

      return <Text testID="ready">ready</Text>;
    };

    render(
      <AuthProvider>
        <LoginComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_user_data',
        JSON.stringify(mockUser)
      );
    });
  });
});

// ============================================================================
// Biometric Authentication Tests
// ============================================================================

describe('Biometric Authentication', () => {
  test('should check if biometric hardware is available', async () => {
    const BiometricComponent = () => {
      const { isBiometricAvailable } = useAuth();
      const [available, setAvailable] = React.useState<boolean>(false);
      const [checked, setChecked] = React.useState(false);

      React.useEffect(() => {
        if (!checked) {
          isBiometricAvailable().then(setAvailable);
          setChecked(true);
        }
      }, [checked]);

      return <Text testID="biometricAvailable">{available.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('biometricAvailable').props.children).toBe('true');
    });

    expect(LocalAuthentication.hasHardwareAsync).toHaveBeenCalled();
    expect(LocalAuthentication.isEnrolledAsync).toHaveBeenCalled();
  });

  test('should return false when biometric hardware not available', async () => {
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValueOnce(false);

    const BiometricComponent = () => {
      const { isBiometricAvailable } = useAuth();
      const [available, setAvailable] = React.useState<boolean>(false);
      const [checked, setChecked] = React.useState(false);

      React.useEffect(() => {
        if (!checked) {
          isBiometricAvailable().then(setAvailable);
          setChecked(true);
        }
      }, [checked]);

      return <Text testID="biometricAvailable">{available.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('biometricAvailable').props.children).toBe('false');
    });
  });

  test('should return false when no biometric enrolled', async () => {
    (LocalAuthentication.hasHardwareAsync as jest.Mock).mockResolvedValueOnce(true);
    (LocalAuthentication.isEnrolledAsync as jest.Mock).mockResolvedValueOnce(false);

    const BiometricComponent = () => {
      const { isBiometricAvailable } = useAuth();
      const [available, setAvailable] = React.useState<boolean>(false);
      const [checked, setChecked] = React.useState(false);

      React.useEffect(() => {
        if (!checked) {
          isBiometricAvailable().then(setAvailable);
          setChecked(true);
        }
      }, [checked]);

      return <Text testID="biometricAvailable">{available.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('biometricAvailable').props.children).toBe('false');
    });
  });

  test('should authenticate with biometric successfully', async () => {
    const BiometricAuthComponent = () => {
      const { authenticateWithBiometric } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [authAttempted, setAuthAttempted] = React.useState(false);

      const handleAuth = async () => {
        const authResult = await authenticateWithBiometric();
        setResult(authResult);
        setAuthAttempted(true);
      };

      React.useEffect(() => {
        if (!authAttempted) {
          handleAuth();
        }
      }, [authAttempted]);

      return <Text testID="authResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricAuthComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('authResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(true);
    });

    expect(LocalAuthentication.authenticateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        promptMessage: 'Authenticate to access Atom',
      })
    );
  });

  test('should handle biometric authentication failure', async () => {
    (LocalAuthentication.authenticateAsync as jest.Mock).mockResolvedValueOnce({
      success: false,
      error: 'not_authenticated',
    });

    const BiometricAuthComponent = () => {
      const { authenticateWithBiometric } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [authAttempted, setAuthAttempted] = React.useState(false);

      const handleAuth = async () => {
        const authResult = await authenticateWithBiometric();
        setResult(authResult);
        setAuthAttempted(true);
      };

      React.useEffect(() => {
        if (!authAttempted) {
          handleAuth();
        }
      }, [authAttempted]);

      return <Text testID="authResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricAuthComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('authResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Biometric authentication failed');
    });
  });

  test('should handle biometric user cancellation', async () => {
    const mockError = new Error('User cancelled');
    (mockError as any).code = 'user_cancel';
    (LocalAuthentication.authenticateAsync as jest.Mock).mockRejectedValueOnce(mockError);

    const BiometricAuthComponent = () => {
      const { authenticateWithBiometric } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [authAttempted, setAuthAttempted] = React.useState(false);

      const handleAuth = async () => {
        const authResult = await authenticateWithBiometric();
        setResult(authResult);
        setAuthAttempted(true);
      };

      React.useEffect(() => {
        if (!authAttempted) {
          handleAuth();
        }
      }, [authAttempted]);

      return <Text testID="authResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricAuthComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('authResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Cancelled by user');
    });
  });

  test('should register biometric with backend', async () => {
    // First login to set access token
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValueOnce(mockAccessToken);

    const BiometricComponent = () => {
      const { registerBiometric } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [registerAttempted, setRegisterAttempted] = React.useState(false);

      const handleRegister = async () => {
        const regResult = await registerBiometric('public_key_123');
        setResult(regResult);
        setRegisterAttempted(true);
      };

      React.useEffect(() => {
        if (!registerAttempted) {
          handleRegister();
        }
      }, [registerAttempted]);

      return <Text testID="registerResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <BiometricComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('registerResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(true);
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/mobile/biometric/register'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Authorization': `Bearer ${mockAccessToken}`,
        }),
        body: expect.stringContaining('public_key_123'),
      })
    );
  });
});

// ============================================================================
// Token Refresh Tests
// ============================================================================

describe('Token Refresh', () => {
  test('should refresh access token successfully', async () => {
    const newAccessToken = 'new_access_token_789';
    const newRefreshToken = 'new_refresh_token_012';

    (SecureStore.getItemAsync as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_refresh_token') return Promise.resolve(mockRefreshToken);
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
      }),
    });

    const TokenRefreshComponent = () => {
      const { refreshToken } = useAuth();
      const [success, setSuccess] = React.useState<boolean>(false);
      const [refreshAttempted, setRefreshAttempted] = React.useState(false);

      const handleRefresh = async () => {
        const result = await refreshToken();
        setSuccess(result);
        setRefreshAttempted(true);
      };

      React.useEffect(() => {
        if (!refreshAttempted) {
          handleRefresh();
        }
      }, [refreshAttempted]);

      return <Text testID="refreshResult">{success.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <TokenRefreshComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('refreshResult').props.children).toBe('true');
    });

    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'atom_access_token',
      newAccessToken
    );
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'atom_refresh_token',
      newRefreshToken
    );
  });

  test('should fail to refresh when no refresh token exists', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);

    const TokenRefreshComponent = () => {
      const { refreshToken } = useAuth();
      const [success, setSuccess] = React.useState<boolean>(false);
      const [refreshAttempted, setRefreshAttempted] = React.useState(false);

      const handleRefresh = async () => {
        const result = await refreshToken();
        setSuccess(result);
        setRefreshAttempted(true);
      };

      React.useEffect(() => {
        if (!refreshAttempted) {
          handleRefresh();
        }
      }, [refreshAttempted]);

      return <Text testID="refreshResult">{success.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <TokenRefreshComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('refreshResult').props.children).toBe('false');
    });
  });

  test('should fail to refresh when backend returns error', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_refresh_token') return Promise.resolve(mockRefreshToken);
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    const TokenRefreshComponent = () => {
      const { refreshToken } = useAuth();
      const [success, setSuccess] = React.useState<boolean>(false);
      const [refreshAttempted, setRefreshAttempted] = React.useState(false);

      const handleRefresh = async () => {
        const result = await refreshToken();
        setSuccess(result);
        setRefreshAttempted(true);
      };

      React.useEffect(() => {
        if (!refreshAttempted) {
          handleRefresh();
        }
      }, [refreshAttempted]);

      return <Text testID="refreshResult">{success.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <TokenRefreshComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('refreshResult').props.children).toBe('false');
    });
  });
});

// ============================================================================
// Logout Tests
// ============================================================================

describe('Logout', () => {
  test('should clear tokens and user data on logout', async () => {
    // Setup authenticated state
    (SecureStore.getItemAsync as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_token_expiry') return Promise.resolve((Date.now() + 3600000).toString());
      return Promise.resolve(null);
    });

    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    const LogoutComponent = () => {
      const { logout, isAuthenticated } = useAuth();

      return (
        <View>
          <Text testID="authStatus">{isAuthenticated ? 'authenticated' : 'not authenticated'}</Text>
          <Pressable testID="logoutButton" onPress={logout} />
        </View>
      );
    };

    const { getByTestId } = render(
      <AuthProvider>
        <LogoutComponent />
      </AuthProvider>
    );

    // Wait for initial auth state
    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('authenticated');
    }, { timeout: 5000 });

    // Clear mocks before logout
    jest.clearAllMocks();

    // Trigger logout
    act(() => {
      getByTestId('logoutButton').props.onPress();
    });

    await waitFor(() => {
      expect(getByTestId('authStatus').props.children).toBe('not authenticated');
    });

    // Verify tokens were deleted
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('atom_access_token');
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('atom_refresh_token');
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('atom_token_expiry');
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_user_data');
  });

  test('should call backend logout endpoint when logged in', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(mockAccessToken);

    const LogoutComponent = () => {
      const { logout } = useAuth();
      const [done, setDone] = React.useState(false);

      const handleLogout = async () => {
        await logout();
        setDone(true);
      };

      React.useEffect(() => {
        handleLogout();
      }, []);

      return <Text testID="done">{done.toString()}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <LogoutComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getByTestId('done').props.children).toBe('true');
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/mobile/logout'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Authorization': `Bearer ${mockAccessToken}`,
        }),
      })
    );
  });
});

// ============================================================================
// Authentication State Persistence Tests
// ============================================================================

describe('Authentication State Persistence', () => {
  test('should restore authentication state from stored tokens', async () => {
    const now = Date.now();
    const futureExpiry = now + 3600000; // 1 hour from now

    (SecureStore.getItemAsync as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_token_expiry') return Promise.resolve(futureExpiry.toString());
      return Promise.resolve(null);
    });

    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    const { getByTestId } = renderWithAuthProvider();

    await waitFor(() => {
      expect(getByTestId('isAuthenticated').props.children).toBe('true');
      expect(getByTestId('user').props.children).toBe(JSON.stringify(mockUser));
    });
  });

  test('should not authenticate when token is expired', async () => {
    const pastExpiry = Date.now() - 1000; // 1 second ago

    (SecureStore.getItemAsync as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_token_expiry') return Promise.resolve(pastExpiry.toString());
      if (key === 'atom_refresh_token') return Promise.resolve(mockRefreshToken);
      return Promise.resolve(null);
    });

    // Token refresh will fail
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    const { getByTestId } = renderWithAuthProvider();

    await waitFor(() => {
      expect(getByTestId('isAuthenticated').props.children).toBe('false');
    });

    // Verify expired tokens were cleared
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('atom_access_token');
  });

  test('should refresh token when expiring soon (< 5 minutes)', async () => {
    const soonExpiry = Date.now() + 4 * 60 * 1000; // 4 minutes from now
    const newAccessToken = 'new_access_token_789';

    (SecureStore.getItemAsync as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_access_token') return Promise.resolve(mockAccessToken);
      if (key === 'atom_token_expiry') return Promise.resolve(soonExpiry.toString());
      if (key === 'atom_refresh_token') return Promise.resolve(mockRefreshToken);
      return Promise.resolve(null);
    });

    (AsyncStorage.getItem as jest.Mock).mockImplementation((key) => {
      if (key === 'atom_user_data') return Promise.resolve(JSON.stringify(mockUser));
      return Promise.resolve(null);
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: newAccessToken,
        refresh_token: mockRefreshToken,
      }),
    });

    const { getByTestId } = renderWithAuthProvider();

    await waitFor(() => {
      expect(getByTestId('isAuthenticated').props.children).toBe('true');
    });

    // Verify token was refreshed
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/refresh'),
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'atom_access_token',
      newAccessToken
    );
  });
});

// ============================================================================
// Device Registration Tests
// ============================================================================

describe('Device Registration', () => {
  test('should register device with push token', async () => {
    const deviceId = 'device_123';
    const pushToken = 'push_token_abc';

    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(mockAccessToken);

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        device_id: deviceId,
      }),
    });

    const DeviceComponent = () => {
      const { registerDevice } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; deviceId?: string; error?: string } | null>(null);
      const [registerAttempted, setRegisterAttempted] = React.useState(false);

      const handleRegister = async () => {
        const regResult = await registerDevice(pushToken);
        setResult(regResult);
        setRegisterAttempted(true);
      };

      React.useEffect(() => {
        if (!registerAttempted) {
          handleRegister();
        }
      }, [registerAttempted]);

      return <Text testID="registerResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('registerResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(true);
      expect(result.deviceId).toBe(deviceId);
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/mobile/notifications/register'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Authorization': `Bearer ${mockAccessToken}`,
        }),
        body: expect.stringContaining(pushToken),
      })
    );

    expect(AsyncStorage.setItem).toHaveBeenCalledWith('atom_device_id', deviceId);
  });

  test('should fail device registration when not authenticated', async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);

    const DeviceComponent = () => {
      const { registerDevice } = useAuth();
      const [result, setResult] = React.useState<{ success: boolean; error?: string } | null>(null);
      const [registerAttempted, setRegisterAttempted] = React.useState(false);

      const handleRegister = async () => {
        const regResult = await registerDevice('push_token');
        setResult(regResult);
        setRegisterAttempted(true);
      };

      React.useEffect(() => {
        if (!registerAttempted) {
          handleRegister();
        }
      }, [registerAttempted]);

      return <Text testID="registerResult">{result ? JSON.stringify(result) : 'waiting'}</Text>;
    };

    const { getByTestId } = render(
      <AuthProvider>
        <DeviceComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      const resultText = getByTestId('registerResult').props.children;
      const result = JSON.parse(resultText as string);
      expect(result.success).toBe(false);
      expect(result.error).toBe('Not authenticated');
    });
  });
});
