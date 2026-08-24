/**
 * Round 82 — mobile journey fixes (M1b gating, M2 token key, M3 reset URL).
 *
 * M1b. AuthNavigator must render the Login flow when unauthenticated and the
 *      main tabs when authenticated.
 * M2.  deviceSocketService.connect() and notificationService.getAuthToken()
 *      read the legacy 'auth_token' storage key, which nothing writes since
 *      the secure-storage migration standardized on 'atom_access_token' —
 *      both could never authenticate.
 * M3.  ForgotPasswordScreen POSTed to /api/auth/password/reset; the backend
 *      route is /api/auth/reset-password. The 404 was swallowed by the
 *      anti-enumeration success path so no reset email was ever sent.
 */
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

// --- Auth state controlled per-test -----------------------------------------
const authState = { isAuthenticated: false, isLoading: false };

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => authState,
  AuthProvider: ({ children }: any) => children,
}));

// --- Auth gating (real AuthNavigator) ----------------------------------------
const textMarker = (label: string) =>
  function Marker() {
    const { Text } = require('react-native');
    return <Text>{label}</Text>;
  };

jest.mock('../../navigation/AppNavigator', () => ({
  AppNavigator: () => {
    const { Text } = require('react-native');
    return <Text>MAIN_APP_MARKER</Text>;
  },
}));
jest.mock('../../screens/auth', () => ({
  LoginScreen: () => {
    const { Text } = require('react-native');
    return <Text>LOGIN_SCREEN_MARKER</Text>;
  },
  RegisterScreen: () => null,
  ForgotPasswordScreen: () => null,
  BiometricAuthScreen: () => null,
}));

jest.mock('@react-navigation/native', () => ({
  NavigationContainer: ({ children }: any) => children,
  DarkTheme: {},
  DefaultTheme: {},
  Linking: {},
  useNavigation: () => ({ navigate: jest.fn(), goBack: jest.fn() }),
  useRoute: () => ({ params: {} }),
}));
jest.mock('@react-navigation/native-stack', () => {
  const React = require('react');
  return {
    createNativeStackNavigator: () => ({
      Navigator: ({ children }: any) => <>{children}</>,
      Screen: ({ component }: any) => React.createElement(component),
    }),
  };
});

describe('M1b — AuthNavigator gates login vs main on auth state', () => {
  function renderAuthNav() {
    const { AuthNavigator } = require('../../navigation/AuthNavigator');
    return render(<AuthNavigator />);
  }

  it('shows the Login screen when unauthenticated', () => {
    authState.isAuthenticated = false;
    const { getByText } = renderAuthNav();
    expect(getByText('LOGIN_SCREEN_MARKER')).toBeTruthy();
  });

  it('shows the main app when authenticated', () => {
    authState.isAuthenticated = true;
    const { getByText, queryByText } = renderAuthNav();
    expect(getByText('MAIN_APP_MARKER')).toBeTruthy();
    expect(queryByText('LOGIN_SCREEN_MARKER')).toBeNull();
  });
});

// ============================================================================
// M2 — device socket / notifications authenticate with the canonical token key
// ============================================================================

jest.mock('../../storage/secureTokenStorage', () => ({
  secureGet: jest.fn(),
  secureSet: jest.fn(),
  secureDelete: jest.fn(),
}));
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({ on: jest.fn(), disconnect: jest.fn(), emit: jest.fn() })),
}));
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(async () => 'device-node-1'),
  setItem: jest.fn(async () => undefined),
}));
jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  getPermissionsAsync: jest.fn(async () => ({ granted: true, status: 'granted' })),
  requestPermissionsAsync: jest.fn(async () => ({ granted: true, status: 'granted' })),
}));
jest.mock('expo-device', () => ({ deviceName: 'test-device' }));
jest.mock('expo-camera', () => ({
  getCameraPermissionsAsync: jest.fn(async () => ({ granted: true, status: 'granted' })),
}));
jest.mock('expo-location', () => ({
  getForegroundPermissionsAsync: jest.fn(async () => ({ granted: true, status: 'granted' })),
}));
jest.mock('expo-file-system', () => ({
  documentDirectory: '/tmp/',
  getInfoAsync: jest.fn(async () => ({ exists: false })),
}));

describe('M2 — deviceSocket uses atom_access_token', () => {
  it('connects with the token stored under atom_access_token', async () => {
    const { secureGet } = require('../../storage/secureTokenStorage');
    const { io } = require('socket.io-client');
    secureGet.mockImplementation(async (key: string) =>
      key === 'atom_access_token' ? 'tok-123' : null
    );

    const { default: deviceSocketService } =
      require('../../services/deviceSocket');
    deviceSocketService.disconnect();
    const ok = await deviceSocketService.connect();

    expect(ok).toBe(true);
    expect(io).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ query: { token: 'tok-123' } })
    );
  });
});

describe('M2b — notificationService uses atom_access_token', () => {
  it('getAuthToken reads the canonical key (source tripwire)', () => {
    // The method resolves storageService via a dynamic import(), which the
    // CJS jest transform cannot execute; lock the storage key at source level
    // instead. 'auth_token' is legacy and never written since the
    // secure-storage migration (#6).
    const fs = require('fs');
    const src = fs.readFileSync(
      require.resolve('../../services/notificationService'),
      'utf8'
    );
    expect(src).toMatch(/['"]atom_access_token['"]/);
    expect(src).not.toMatch(/getStringAsync\(['"]auth_token['"]/);
  });
});

// ============================================================================
// M3 — forgot-password hits the real backend endpoint
// ============================================================================

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(async () => null),
  setItemAsync: jest.fn(async () => undefined),
}));
jest.mock('expo-constants', () => ({
  __esModule: true,
  default: { expoConfig: { extra: { apiUrl: 'http://test-api' } } },
}));
jest.mock('@expo/vector-icons', () => ({ Ionicons: 'Ionicons' }));

describe('M3 — ForgotPasswordScreen reset endpoint', () => {
  it('POSTs to /api/auth/reset-password (the backend route)', async () => {
    const fetchMock = jest.fn(
      async () => ({ ok: true, status: 200, json: async () => ({}) }) as any
    );
    global.fetch = fetchMock as any;

    const { ForgotPasswordScreen } =
      require('../../screens/auth/ForgotPasswordScreen');
    const { getByPlaceholderText, getByText } = render(
      <ForgotPasswordScreen
        navigation={{ navigate: jest.fn(), goBack: jest.fn() } as any}
      />
    );

    fireEvent.changeText(getByPlaceholderText(/email/i), 'user@example.com');
    fireEvent.press(getByText(/send reset link/i));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe('http://test-api/api/auth/reset-password');
  });
});
