/**
 * Navigation Mock Helpers
 *
 * Functional screen mock components for testing React Navigation.
 * Replaces string mocks with actual React components that render
 * with testIDs for reliable test assertions.
 *
 * Follows Phase 136 deviceMocks.ts pattern - reusable factories,
 * consistent naming, JSDoc comments.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

/**
 * Create a mock screen component with testID
 *
 * Returns a functional React component that renders a View with
 * a testID for testing. The component receives route and navigation
 * props like a real screen.
 *
 * @param screenName - Name of the screen for display
 * @param testId - testID attribute for testing queries
 * @returns Mock screen component
 *
 * @example
 * ```typescript
 * const MockLoginScreen = createMockScreen('Login', 'login-screen');
 * // Renders: <View testID="login-screen" screenName="Login" />
 * ```
 */
export const createMockScreen = (screenName: string, testId: string) => {
  return function MockScreen({ route, navigation }: any) {
    return (
      <View testID={testId} style={styles.mockScreen}>
        <Text testID={`${testId}-name`}>{screenName}</Text>
        {route?.params && (
          <Text testID={`${testId}-params`} style={styles.paramsText}>
            {JSON.stringify(route.params)}
          </Text>
        )}
      </View>
    );
  };
};

/**
 * Mock all auth screens with functional components
 *
 * Replaces string mocks (jest.mock('../Screen', () => 'Screen'))
 * with functional components that render with testIDs.
 *
 * Call this at the top of test files before rendering navigation:
 * ```typescript
 * import { mockAllScreens } from '../helpers/navigationMocks';
 * mockAllScreens();
 * ```
 *
 * TestIDs follow pattern: {screen-name}-screen
 * - Login: 'login-screen'
 * - Register: 'register-screen'
 * - ForgotPassword: 'forgot-password-screen'
 * - BiometricAuth: 'biometric-auth-screen'
 */
export const mockAllScreens = () => {
  // Auth screens
  jest.mock('../../screens/auth/LoginScreen', () =>
    createMockScreen('Login', 'login-screen')
  );
  jest.mock('../../screens/auth/RegisterScreen', () =>
    createMockScreen('Register', 'register-screen')
  );
  jest.mock('../../screens/auth/ForgotPasswordScreen', () =>
    createMockScreen('ForgotPassword', 'forgot-password-screen')
  );
  jest.mock('../../screens/auth/BiometricAuthScreen', () =>
    createMockScreen('BiometricAuth', 'biometric-auth-screen')
  );

  // Workflow screens
  jest.mock('../../screens/workflows/WorkflowsListScreen', () =>
    createMockScreen('WorkflowsList', 'workflows-list-screen')
  );
  jest.mock('../../screens/workflows/WorkflowDetailScreen', () =>
    createMockScreen('WorkflowDetail', 'workflow-detail-screen')
  );

  // Analytics screens
  jest.mock('../../screens/analytics/AnalyticsDashboardScreen', () =>
    createMockScreen('AnalyticsDashboard', 'analytics-dashboard-screen')
  );

  // Agent screens
  jest.mock('../../screens/agents/AgentListScreen', () =>
    createMockScreen('AgentList', 'agent-list-screen')
  );
  jest.mock('../../screens/agents/AgentChatScreen', () =>
    createMockScreen('AgentChat', 'agent-chat-screen')
  );

  // Chat screens
  jest.mock('../../screens/chat/ChatTabScreen', () =>
    createMockScreen('ChatTab', 'chat-tab-screen')
  );

  // Settings screens
  jest.mock('../../screens/settings/SettingsScreen', () =>
    createMockScreen('Settings', 'settings-screen')
  );
};

/**
 * Create a mock screen with custom content
 *
 * Creates a mock screen that renders custom content instead of
 * just the screen name. Useful for testing screens with specific
 * content requirements.
 *
 * @param testId - testID attribute for testing queries
 * @param content - React element to render as screen content
 * @returns Mock screen component
 *
 * @example
 * ```typescript
 * const MockWorkflowDetail = createMockScreenWithContent(
 *   'workflow-detail-screen',
 *   <Text testID="workflow-title">Test Workflow</Text>
 * );
 * ```
 */
export const createMockScreenWithContent = (testId: string, content: React.ReactNode) => {
  return function MockScreen({ route, navigation }: any) {
    return (
      <View testID={testId} style={styles.mockScreen}>
        {content}
        {route?.params && (
          <Text testID={`${testId}-params`} style={styles.paramsText}>
            {JSON.stringify(route.params)}
          </Text>
        )}
      </View>
    );
  };
};

/**
 * Create a mock screen with navigation callback
 *
 * Creates a mock screen that calls a navigation function when
 * rendered. Useful for testing navigation transitions.
 *
 * @param testId - testID attribute for testing queries
 * @param screenName - Name of the screen for display
 * @param onNavigate - Callback function to call with navigation prop
 * @returns Mock screen component
 *
 * @example
 * ```typescript
 * const MockLoginScreen = createMockScreenWithNavigation(
 *   'login-screen',
 *   'Login',
 *   (navigation) => {
 *     // Test can verify navigation was called
 *     expect(navigation.navigate).toHaveBeenCalledWith('Register');
 *   }
 * );
 * ```
 */
export const createMockScreenWithNavigation = (
  testId: string,
  screenName: string,
  onNavigate?: (navigation: any) => void
) => {
  return function MockScreen({ route, navigation }: any) {
    React.useEffect(() => {
      if (onNavigate) {
        onNavigate(navigation);
      }
    }, [navigation]);

    return (
      <View testID={testId} style={styles.mockScreen}>
        <Text testID={`${testId}-name`}>{screenName}</Text>
        {route?.params && (
          <Text testID={`${testId}-params`} style={styles.paramsText}>
            {JSON.stringify(route.params)}
          </Text>
        )}
      </View>
    );
  };
};

/**
 * Mock AppNavigator for auth flow testing
 *
 * Returns a mock AppNavigator component that renders a View with
 * testID for testing. Used when testing AuthNavigator's transition
 * to main app.
 *
 * @returns Mock AppNavigator component
 */
export const createMockAppNavigator = () => {
  return function MockAppNavigator() {
    return <View testID="app-navigator" style={styles.mockScreen} />;
  };
};

/**
 * Mock AuthContext for testing authentication state
 *
 * Creates a mock AuthContext with controlled authentication state.
 * Use this to test conditional rendering based on auth state.
 *
 * @param isAuthenticated - Whether user is authenticated
 * @param isLoading - Whether auth state is loading
 * @returns Mock AuthContext value
 *
 * @example
 * ```typescript
 * const mockAuthContext = createMockAuthContext(true, false);
 * jest.mock('../../contexts/AuthContext', () => ({
 *   useAuth: () => mockAuthContext
 * }));
 * ```
 */
export const createMockAuthContext = (
  isAuthenticated: boolean = false,
  isLoading: boolean = false
) => {
  return {
    isAuthenticated,
    isLoading,
    user: isAuthenticated ? { id: 'test-user-123', email: 'test@example.com' } : null,
    token: isAuthenticated ? 'test-token-abc123' : null,
    login: jest.fn(),
    logout: jest.fn(),
    register: jest.fn(),
    refreshToken: jest.fn(),
  };
};

/**
 * Mock Ionicons for navigation testing
 *
 * Mocks the @expo/vector-icons Ionicons component to avoid
 * import errors in navigation tests.
 */
export const mockIonicons = () => {
  jest.mock('@expo/vector-icons', () => ({
    Ionicons: 'Ionicons',
  }));
};

const styles = StyleSheet.create({
  mockScreen: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
    padding: 16,
  },
  paramsText: {
    marginTop: 8,
    fontSize: 12,
    color: '#666',
    fontFamily: 'monospace',
  },
});
