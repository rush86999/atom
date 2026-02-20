/**
 * Custom Test Render Function for Atom Mobile Tests
 *
 * This file provides a custom render function that wraps components with all necessary
 * providers (Auth, WebSocket, Device, Navigation) for consistent testing.
 *
 * Features:
 * - Custom render with all providers
 * - Mock navigation prop
 * - Wrapper component with context providers
 * - Reusable render hooks
 */

import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';

// Mock contexts
import { AuthProvider } from '../contexts/AuthContext';
import { WebSocketProvider } from '../contexts/WebSocketContext';
import { DeviceProvider } from '../contexts/DeviceContext';

// ============================================================================
// Types
// ============================================================================

type MockNavigation = {
  navigate: jest.Mock;
  goBack: jest.Mock;
  replace: jest.Mock;
  reset: jest.Mock;
  dispatch: jest.Mock;
  canGoBack: jest.Mock;
  isFocused: jest.Mock;
  getId: jest.Mock;
  getState: jest.Mock;
  getParent: jest.Mock;
};

type CustomRenderOptions = Omit<RenderOptions, 'wrapper'> & {
  navigation?: Partial<MockNavigation>;
  authContext?: any;
  webSocketContext?: any;
  deviceContext?: any;
};

// ============================================================================
// Mock Navigation
// ============================================================================

const createMockNavigation = (overrides: Partial<MockNavigation> = {}): MockNavigation => ({
  navigate: jest.fn(),
  goBack: jest.fn(),
  replace: jest.fn(),
  reset: jest.fn(),
  dispatch: jest.fn(),
  canGoBack: jest.fn(() => true),
  isFocused: jest.fn(() => true),
  getId: jest.fn(() => 'mock-screen-id'),
  getState: jest.fn(() => ({ key: 'mock-key', routeName: 'MockRoute', index: 0 })),
  getParent: jest.fn(() => ({})),
  ...overrides,
});

// ============================================================================
// Default Context Values
// ============================================================================

const defaultAuthContext = {
  isAuthenticated: true,
  isLoading: false,
  user: {
    id: 'test-user-id',
    email: 'test@example.com',
    name: 'Test User',
    avatar: null,
  },
  token: 'test-auth-token',
  login: jest.fn(),
  logout: jest.fn(),
  register: jest.fn(),
  refreshToken: jest.fn(),
  biometricAuth: jest.fn(),
};

const defaultWebSocketContext = {
  isConnected: true,
  isConnecting: false,
  reconnectAttempts: 0,
  connect: jest.fn(),
  disconnect: jest.fn(),
  send: jest.fn(),
  on: jest.fn(),
  off: jest.fn(),
  joinRoom: jest.fn(),
  leaveRoom: jest.fn(),
};

const defaultDeviceContext = {
  deviceInfo: {
    id: 'test-device-id',
    name: 'Test Device',
    platform: 'ios',
    osVersion: '16.0',
    appVersion: '1.0.0',
  },
  permissions: {
    camera: 'granted',
    location: 'granted',
    notifications: 'granted',
    biometric: 'granted',
  },
  requestPermission: jest.fn(),
  checkPermission: jest.fn(),
  syncDevice: jest.fn(),
};

// ============================================================================
// All Providers Wrapper
// ============================================================================

const AllProviders: React.FC<{
  children: React.ReactNode;
  authContext?: any;
  webSocketContext?: any;
  deviceContext?: any;
}> = ({
  children,
  authContext = defaultAuthContext,
  webSocketContext = defaultWebSocketContext,
  deviceContext = defaultDeviceContext,
}) => {
  return (
    <NavigationContainer>
      <AuthProvider value={authContext}>
        <WebSocketProvider value={webSocketContext}>
          <DeviceProvider value={deviceContext}>
            {children}
          </DeviceProvider>
        </WebSocketProvider>
      </AuthProvider>
    </NavigationContainer>
  );
};

// ============================================================================
// Custom Render Function
// ============================================================================

/**
 * Custom render function that wraps components with all providers
 *
 * @param ui - Component to render
 * @param options - Render options including context overrides
 * @returns Render result with navigation mock
 */
export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {}
) {
  const {
    navigation: navigationOverrides,
    authContext,
    webSocketContext,
    deviceContext,
    ...renderOptions
  } = options;

  const mockNavigation = createMockNavigation(navigationOverrides);

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AllProviders
      authContext={authContext}
      webSocketContext={webSocketContext}
      deviceContext={deviceContext}
    >
      {children}
    </AllProviders>
  );

  const result = render(ui, { wrapper, ...renderOptions });

  return {
    ...result,
    navigation: mockNavigation,
  };
}

/**
 * Simplified render without providers for isolated component tests
 */
export function renderIn isolation(ui: ReactElement, options?: RenderOptions) {
  return render(ui, options);
}

/**
 * Render with mock navigation prop (for screens that need navigation)
 */
export function renderWithNavigation(
  ui: ReactElement,
  options: CustomRenderOptions = {}
) {
  const {
    navigation: navigationOverrides,
    authContext,
    webSocketContext,
    deviceContext,
    ...renderOptions
  } = options;

  const mockNavigation = createMockNavigation(navigationOverrides);

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AllProviders
      authContext={authContext}
      webSocketContext={webSocketContext}
      deviceContext={deviceContext}
    >
      {children}
    </AllProviders>
  );

  // Clone element and add navigation prop
  const elementWithNavigation = React.cloneElement(ui, {
    navigation: mockNavigation,
  } as any);

  const result = render(elementWithNavigation as ReactElement, {
    wrapper,
    ...renderOptions,
  });

  return {
    ...result,
    navigation: mockNavigation,
  };
}

/**
 * Helper to create mock navigation props for typed screens
 */
export function createMockNavigationProps<T extends Record<string, any>>(
  route: T,
  overrides: Partial<MockNavigation> = {}
): NativeStackScreenProps<any, any, any> {
  const mockNavigation = createMockNavigation(overrides);

  return {
    navigation: mockNavigation as any,
    route: {
      key: 'mock-route-key',
      name: 'MockRoute',
      params: route,
    } as any,
  };
}

// ============================================================================
// Re-exports
// ============================================================================

export * from '@testing-library/react-native';

// ============================================================================
// Default export
// ============================================================================

export default renderWithProviders;
