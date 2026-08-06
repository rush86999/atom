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
import { View, Text } from 'react-native';

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
      <View testID={testId} >
        <Text testID={`${testId}-name`}>{screenName}</Text>
        {route?.params && (
          <Text testID={`${testId}-params`} >
            {JSON.stringify(route.params)}
          </Text>
        )}
      </View>
    );
  };
};

/**
 * Mock all auth/workflow/agent/chat/settings screens with functional components
 *
 * Replaces string mocks (jest.mock('../Screen', () => 'Screen'))
 * with functional components that render with testIDs.
 *
 * IMPORTANT: this function registers jest.mock factories and MUST be called
 * BEFORE the navigator module (AppNavigator/AuthNavigator) is loaded. ES
 * module imports are executed before the surrounding code, so navigators
 * must be imported lazily via require() AFTER mockAllScreens() runs:
 *
 * ```typescript
 * import { mockAllScreens } from '../helpers/navigationMocks';
 * mockAllScreens();
 * const AppNavigator = require('../../navigation/AppNavigator').default;
 * ```
 *
 * Each factory returns an object keyed by the module's named export so
 * named imports in the navigators resolve to the mock component.
 *
 * TestIDs follow pattern: {screen-name}-screen
 * - Login: 'login-screen'
 * - Register: 'register-screen'
 * - ForgotPassword: 'forgot-password-screen'
 * - BiometricAuth: 'biometric-auth-screen'
 */
export const mockAllScreens = () => {
  const mockScreen = (screenName: string, testId: string, navigateTo?: string | string[]) => {
    const React = require('react');
    const { View, Text, Pressable } = require('react-native');
    const destinations = Array.isArray(navigateTo) ? navigateTo : navigateTo ? [navigateTo] : [];
    return function MockScreen({ route, navigation }: any) {
      // Navigation-state capture hook: tests register
      // global.__atomNavStateCapture to receive the root navigation state
      // (useNavigationState can't be used from outside the navigator tree).
      React.useEffect(() => {
        // Walk up to the root navigator (screen navigation objects expose
        // getParent/getState but not getRootState in react-navigation 6.x)
        let current = navigation;
        let root = null;
        let prev = null;
        while (current && current !== prev) {
          prev = current;
          root = current;
          current = current.getParent?.() || null;
        }
        const capture = () => {
          const state = root?.getState?.();
          const ownState = navigation?.getState?.();
          if (typeof global.__atomNavStateCapture === 'function' && state) {
            // The root getState() does not include nested navigator states,
            // but the container's root state does. Rebuild that shape for the
            // focused route (matches getRootState() semantics: lazy tabs have
            // no nested state until visited).
            let fullState = state;
            if (state.type === 'tab' && ownState && ownState !== state) {
              fullState = {
                ...state,
                routes: state.routes.map((r: any, i: number) =>
                  i === state.index ? { ...r, state: ownState } : r
                ),
              };
            }
            global.__atomNavStateCapture(fullState, screenName);
          }
        };
        capture();
        const unsubscribeScreen = navigation?.addListener?.('state', capture);
        const unsubscribeRoot = root?.addListener?.('state', capture);
        return () => {
          unsubscribeScreen?.();
          unsubscribeRoot?.();
        };
      }, [navigation, screenName]);
      return React.createElement(View, { testID: testId, style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: `${testId}-name` }, screenName),
        destinations.map((dest: string) =>
          React.createElement(
            Pressable,
            {
              key: dest,
              testID: `${testId}-nav-${dest}`,
              onPress: () => navigation?.navigate?.(dest),
            },
            React.createElement(Text, null, `Go to ${dest}`)
          )
        )
      );
    };
  };

  // Auth screens (with navigation buttons for auth-flow tests)
  jest.mock('../../screens/auth/LoginScreen', () => ({
    LoginScreen: mockScreen('Login', 'login-screen', ['Register', 'ForgotPassword', 'BiometricAuth']),
  }));

  jest.mock('../../screens/auth/RegisterScreen', () => ({
    RegisterScreen: mockScreen('Register', 'register-screen', 'Login'),
  }));

  jest.mock('../../screens/auth/ForgotPasswordScreen', () => ({
    ForgotPasswordScreen: mockScreen('ForgotPassword', 'forgot-password-screen', 'Login'),
  }));

  jest.mock('../../screens/auth/BiometricAuthScreen', () => ({
    BiometricAuthScreen: mockScreen('BiometricAuth', 'biometric-auth-screen'),
  }));

  // Workflow screens
  jest.mock('../../screens/workflows/WorkflowsListScreen', () => ({
    WorkflowsListScreen: mockScreen('WorkflowsList', 'workflows-list-screen'),
  }));

  jest.mock('../../screens/workflows/WorkflowDetailScreen', () => ({
    WorkflowDetailScreen: mockScreen('WorkflowDetail', 'workflow-detail-screen'),
  }));

  jest.mock('../../screens/workflows/WorkflowTriggerScreen', () => ({
    WorkflowTriggerScreen: mockScreen('WorkflowTrigger', 'workflow-trigger-screen'),
  }));

  jest.mock('../../screens/workflows/ExecutionProgressScreen', () => ({
    ExecutionProgressScreen: mockScreen('ExecutionProgress', 'execution-progress-screen'),
  }));

  jest.mock('../../screens/workflows/WorkflowLogsScreen', () => ({
    WorkflowLogsScreen: mockScreen('WorkflowLogs', 'workflow-logs-screen'),
  }));

  // Analytics screens
  jest.mock('../../screens/analytics/AnalyticsDashboardScreen', () => ({
    AnalyticsDashboardScreen: mockScreen('AnalyticsDashboard', 'analytics-dashboard-screen'),
  }));

  // Agent screens
  jest.mock('../../screens/agent/AgentListScreen', () => ({
    AgentListScreen: mockScreen('AgentList', 'agent-list-screen'),
  }));

  jest.mock('../../screens/agent/AgentChatScreen', () => ({
    AgentChatScreen: mockScreen('AgentChat', 'agent-chat-screen'),
  }));

  // Chat screens (barrel export)
  jest.mock('../../screens/chat', () => ({
    ChatTabScreen: mockScreen('ChatTab', 'chat-tab-screen'),
  }));

  // Settings screens
  jest.mock('../../screens/settings/SettingsScreen', () => ({
    SettingsScreen: mockScreen('Settings', 'settings-screen'),
  }));
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
      <View testID={testId} >
        {content}
        {route?.params && (
          <Text testID={`${testId}-params`} >
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
      <View testID={testId} >
        <Text testID={`${testId}-name`}>{screenName}</Text>
        {route?.params && (
          <Text testID={`${testId}-params`} >
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
    return <View testID="app-navigator"  />;
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

/**
 * TestIDs for all mocked screens
 * Use these in tests to query for specific screens
 */
export const SCREEN_TEST_IDS = {
  // Tab screens
  WORKFLOWS_LIST: 'workflows-list-screen',
  ANALYTICS_DASHBOARD: 'analytics-dashboard-screen',
  AGENT_LIST: 'agent-list-screen',
  CHAT_TAB: 'chat-tab-screen',
  SETTINGS: 'settings-screen',

  // Stack screens (WorkflowStack)
  WORKFLOW_DETAIL: 'workflow-detail-screen',
  WORKFLOW_TRIGGER: 'workflow-trigger-screen',
  EXECUTION_PROGRESS: 'execution-progress-screen',
  WORKFLOW_LOGS: 'workflow-logs-screen',

  // Stack screens (AgentStack, ChatStack)
  AGENT_CHAT: 'agent-chat-screen',
} as const;

