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
  jest.mock('../../screens/auth/LoginScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockLoginScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'login-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'login-screen-name' }, 'Login')
      );
    };
  });

  jest.mock('../../screens/auth/RegisterScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockRegisterScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'register-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'register-screen-name' }, 'Register')
      );
    };
  });

  jest.mock('../../screens/auth/ForgotPasswordScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockForgotPasswordScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'forgot-password-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'forgot-password-screen-name' }, 'ForgotPassword')
      );
    };
  });

  jest.mock('../../screens/auth/BiometricAuthScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockBiometricAuthScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'biometric-auth-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'biometric-auth-screen-name' }, 'BiometricAuth')
      );
    };
  });

  // Workflow screens
  jest.mock('../../screens/workflows/WorkflowsListScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockWorkflowsListScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'workflows-list-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'workflows-list-screen-name' }, 'WorkflowsList')
      );
    };
  });

  jest.mock('../../screens/workflows/WorkflowDetailScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockWorkflowDetailScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'workflow-detail-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'workflow-detail-screen-name' }, 'WorkflowDetail')
      );
    };
  });

  jest.mock('../../screens/workflows/WorkflowTriggerScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockWorkflowTriggerScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'workflow-trigger-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'workflow-trigger-screen-name' }, 'WorkflowTrigger')
      );
    };
  });

  jest.mock('../../screens/workflows/ExecutionProgressScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockExecutionProgressScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'execution-progress-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'execution-progress-screen-name' }, 'ExecutionProgress')
      );
    };
  });

  jest.mock('../../screens/workflows/WorkflowLogsScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockWorkflowLogsScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'workflow-logs-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'workflow-logs-screen-name' }, 'WorkflowLogs')
      );
    };
  });

  // Analytics screens
  jest.mock('../../screens/analytics/AnalyticsDashboardScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockAnalyticsDashboardScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'analytics-dashboard-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'analytics-dashboard-screen-name' }, 'AnalyticsDashboard')
      );
    };
  });

  // Agent screens
  jest.mock('../../screens/agent/AgentListScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockAgentListScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'agent-list-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'agent-list-screen-name' }, 'AgentList')
      );
    };
  });

  jest.mock('../../screens/agent/AgentChatScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockAgentChatScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'agent-chat-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'agent-chat-screen-name' }, 'AgentChat')
      );
    };
  });

  // Chat screens (barrel export)
  jest.mock('../../screens/chat', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return {
      ChatTabScreen: function MockChatTabScreen({ route, navigation }: any) {
        return React.createElement(View, { testID: 'chat-tab-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
          React.createElement(Text, { testID: 'chat-tab-screen-name' }, 'ChatTab')
        );
      }
    };
  });

  // Settings screens
  jest.mock('../../screens/settings/SettingsScreen', () => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return function MockSettingsScreen({ route, navigation }: any) {
      return React.createElement(View, { testID: 'settings-screen', style: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f5f5f5', padding: 16 } },
        React.createElement(Text, { testID: 'settings-screen-name' }, 'Settings')
      );
    };
  });
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

