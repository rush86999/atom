/**
 * Round 82 / M1 — App boot wiring.
 *
 * App.tsx used to render <AppNavigator /> directly inside its own
 * NavigationContainer, so <AuthNavigator /> — the only component that gates
 * Login vs Main on authentication state and registers deep-link config —
 * was dead code: the app booted straight into main tabs with no way to log
 * in. src/hooks/useColorScheme also did not exist (phantom import,
 * bundle-breaking).
 */
import React from 'react';
import { render } from '@testing-library/react-native';

const authState = { isAuthenticated: false, isLoading: false };

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => authState,
  AuthProvider: ({ children }: any) => children,
}));

jest.mock('../../contexts/WebSocketContext', () => ({
  WebSocketProvider: ({ children }: any) => children,
  useWebSocket: () => ({ socket: null }),
}));

// Markers: App must delegate to AuthNavigator, never mount tabs directly.
jest.mock('../../navigation/AuthNavigator', () => ({
  AuthNavigator: () => {
    const { Text } = require('react-native');
    return <Text>AUTH_NAV_MARKER</Text>;
  },
}));
jest.mock('../../navigation/AppNavigator', () => ({
  AppNavigator: () => {
    const { Text } = require('react-native');
    return <Text>MAIN_APP_MARKER</Text>;
  },
}));

jest.mock('@react-navigation/native', () => ({
  NavigationContainer: ({ children }: any) => children,
  DarkTheme: {},
  DefaultTheme: {},
  useNavigation: () => ({ navigate: jest.fn(), goBack: jest.fn() }),
  useRoute: () => ({ params: {} }),
}));

describe('M1 — App boot wiring', () => {
  it('renders through AuthNavigator (auth gating + deep links intact)', () => {
    const App = require('../../../App').default;
    const { getByText, queryByText } = render(<App />);
    expect(getByText('AUTH_NAV_MARKER')).toBeTruthy();
    // The bug: AppNavigator was mounted directly, bypassing auth gating.
    expect(queryByText('MAIN_APP_MARKER')).toBeNull();
  });
});
